import argparse
import os
import json
import time
import requests
from datetime import date
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "klaviyo_api_data.json"
MONTH_LABELS = ["ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26", "jul-26", "ago-26", "sep-26", "oct-26", "nov-26", "dic-26"]

def get_headers(api_key):
    return {
        "Authorization": f"Klaviyo-API-Key {api_key.strip()}",
        "accept": "application/json",
        "revision": "2024-02-15"
    }

def fetch_all_pages(url, headers):
    data = []
    while url:
        try:
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                js = res.json()
                data.extend(js.get("data", []))
                url = js.get("links", {}).get("next")
            else:
                break
        except:
            break
    return data

def get_campaign_ids(api_key):
    print("  -> Extrayendo IDs de Campanas...")
    campaigns = fetch_all_pages("https://a.klaviyo.com/api/campaigns/?fields[campaign]=id", get_headers(api_key))
    return set(c["id"] for c in campaigns)

def get_flow_message_ids(api_key):
    print("  -> Extrayendo IDs de Flows y Mensajes...")
    headers = get_headers(api_key)
    flows = fetch_all_pages("https://a.klaviyo.com/api/flows/?fields[flow]=id", headers)
    msg_ids = set()
    for f in flows:
        actions = fetch_all_pages(f"https://a.klaviyo.com/api/flow-actions/?filter=equals(flow_id,\"{f['id']}\")&fields[flow-action]=id", headers)
        for a in actions:
            msg_ids.add(a["id"])
    return msg_ids

def get_profile_counts(api_key):
    """Count current total and active email profiles through the Profiles API."""
    print("  -> Contando perfiles totales y perfiles activos...")
    url = "https://a.klaviyo.com/api/profiles/?page[size]=100&additional-fields[profile]=subscriptions"
    total = active = 0
    while url:
        response = requests.get(url, headers=get_headers(api_key), timeout=30)
        response.raise_for_status()
        payload = response.json()
        profiles = payload.get("data", [])
        total += len(profiles)
        for profile in profiles:
            attributes = profile.get("attributes", {})
            marketing = attributes.get("subscriptions", {}).get("email", {}).get("marketing", {})
            # Klaviyo: active email profiles can be emailed and are not suppressed.
            if attributes.get("email") and not marketing.get("suppression"):
                active += 1
        url = payload.get("links", {}).get("next")
    return total, active

def profile_snapshots(previous_bu, total, active, snapshot_closed_month):
    """Keep one immutable snapshot for the most recently closed month only."""
    total_history = list(previous_bu.get("total_profiles", [None] * 12))[:12]
    active_history = list(previous_bu.get("active_profiles", [None] * 12))[:12]
    total_history += [None] * (12 - len(total_history))
    active_history += [None] * (12 - len(active_history))
    if snapshot_closed_month:
        # Daily refreshes must never modify a closed month.
        # Klaviyo does not expose this population as a historical aggregate.
        closed_index = date.today().month - 2
        if closed_index >= 0:
            if total_history[closed_index] is None:
                total_history[closed_index] = total
            if active_history[closed_index] is None:
                active_history[closed_index] = active
    return total_history, active_history

def get_metric_id(api_key, name):
    url = "https://a.klaviyo.com/api/metrics/"
    print(f"Buscando metrica: {name}...")
    for attempt in range(2):
        try:
            res = requests.get(url, headers=get_headers(api_key))
            if res.status_code == 200:
                data = res.json().get("data", [])
                for item in data:
                    metric_name = item.get("attributes", {}).get("name", "")
                    if metric_name.lower() == name.lower():
                        return item["id"]
        except:
            time.sleep(2)
    return None

def fetch_aggregate(api_key, metric_id, measurement="unique", group_by=None, allowed_ids=None):
    if not metric_id: return [None]*12
    url = "https://a.klaviyo.com/api/metric-aggregates/"
    payload = {
        "data": {
            "type": "metric-aggregate",
            "attributes": {
                "metric_id": metric_id,
                "interval": "month",
                "timezone": "UTC",
                "filter": [
                    "greater-or-equal(datetime,2026-01-01T00:00:00)",
                    "less-than(datetime,2027-01-01T00:00:00)"
                ],
                "measurements": [measurement]
            }
        }
    }
    
    if group_by:
        payload["data"]["attributes"]["by"] = [group_by]
        
    result_array = [None]*12
    
    for attempt in range(3):
        time.sleep(2)
        try:
            res = requests.post(url, json=payload, headers=get_headers(api_key))
            if res.status_code == 429:
                time.sleep(4)
                continue
            elif res.status_code == 400 and group_by:
                print(f"  -> ADVERTENCIA: '{group_by}' falló. Retornando vacío.")
                break
            elif res.status_code == 200:
                data = res.json().get("data", {}).get("attributes", {})
                dates = data.get("dates", [])
                results_data = data.get("data", [])
                
                sums = [0]*len(dates)
                if group_by:
                    for group in results_data:
                        dim_val = group.get("dimensions", [])
                        if dim_val and dim_val[0]:
                            val_id = dim_val[0]
                            # Si se paso allowed_ids, solo sumar si coincide
                            if allowed_ids is not None and val_id not in allowed_ids:
                                continue
                            vals = group.get("measurements", {}).get(measurement, [])
                            for i, v in enumerate(vals):
                                sums[i] += v
                else:
                    if results_data:
                        sums = results_data[0].get("measurements", {}).get(measurement, [])
                
                for i, d in enumerate(dates):
                    try:
                        month_idx = int(d[5:7]) - 1
                        if 0 <= month_idx < 12 and i < len(sums):
                            result_array[month_idx] = sums[i] if sums[i] else 0
                    except:
                        pass
                break
        except Exception as e:
            time.sleep(4)
            
    # Llenar con 0 hasta el mes actual
    current_month = date.today().month
    for i in range(current_month):
        if result_array[i] is None:
            result_array[i] = 0
            
    return result_array

def process_bu(api_key, bu_name, previous_bu=None, snapshot_closed_month=False):
    print(f"\n=====================================")
    print(f"PROCESANDO API PURA PARA: {bu_name}")
    print(f"=====================================")
    if not api_key:
        raise RuntimeError(f"Falta KLAVIYO_API_KEY para {bu_name}; se cancela para no publicar datos engañosos.")
        
    id_placed = get_metric_id(api_key, "Placed Order")
    id_received = get_metric_id(api_key, "Received Email")
    id_opened = get_metric_id(api_key, "Opened Email")
    id_clicked = get_metric_id(api_key, "Clicked Email")
    
    # Extraer verdaderos IDs de Campana y Flow
    camp_ids = get_campaign_ids(api_key)
    flow_ids = get_flow_message_ids(api_key)
    
    # Revenue (Para Placed Order, Klaviyo usa $attributed_message y $attributed_flow nativamente)
    camp_rev = fetch_aggregate(api_key, id_placed, "sum_value", "$attributed_message")
    flow_rev = fetch_aggregate(api_key, id_placed, "sum_value", "$attributed_flow")
    
    # Emails (Para Received/Opened/Clicked, agrupamos por $message y filtramos localmente por los IDs extraidos)
    camp_recip = fetch_aggregate(api_key, id_received, "unique", "$message", allowed_ids=camp_ids)
    camp_opens = fetch_aggregate(api_key, id_opened, "unique", "$message", allowed_ids=camp_ids)
    camp_clicks = fetch_aggregate(api_key, id_clicked, "unique", "$message", allowed_ids=camp_ids)
    camp_conv = fetch_aggregate(api_key, id_placed, "unique", "$attributed_message")
    
    flow_recip = fetch_aggregate(api_key, id_received, "unique", "$message", allowed_ids=flow_ids)
    flow_opens = fetch_aggregate(api_key, id_opened, "unique", "$message", allowed_ids=flow_ids)
    flow_clicks = fetch_aggregate(api_key, id_clicked, "unique", "$message", allowed_ids=flow_ids)
    flow_conv = fetch_aggregate(api_key, id_placed, "unique", "$attributed_flow")
    
    total_profiles, active_now = get_profile_counts(api_key)
    total_profiles_history, active_profiles = profile_snapshots(
        previous_bu or {}, total_profiles, active_now, snapshot_closed_month
    )
    
    # Gross sales (Solo email)
    gross_sales = [None]*12
    for i in range(12):
        if camp_rev[i] is not None or flow_rev[i] is not None:
            gross_sales[i] = (camp_rev[i] or 0) + (flow_rev[i] or 0)
            
    def safe_div(a, b):
        return (a/b) if (a is not None and b) else 0
    def safe_pct(a, b):
        return (a/b*100) if (a is not None and b) else 0

    camp_open_rate = [ safe_pct(camp_opens[i], camp_recip[i]) for i in range(12) ]
    camp_ctr = [ safe_pct(camp_clicks[i], camp_opens[i]) for i in range(12) ]
    camp_conv_rate = [ safe_pct(camp_conv[i], camp_recip[i]) for i in range(12) ]
    camp_aov = [ safe_div(camp_rev[i], camp_conv[i]) for i in range(12) ]
    camp_usd_per_cust = [ safe_div(camp_rev[i], camp_recip[i]) for i in range(12) ]
    camp_share = [ safe_pct(camp_rev[i], gross_sales[i]) for i in range(12) ]
    
    flow_open_rate = [ safe_pct(flow_opens[i], flow_recip[i]) for i in range(12) ]
    flow_ctr = [ safe_pct(flow_clicks[i], flow_opens[i]) for i in range(12) ]
    flow_conv_rate = [ safe_pct(flow_conv[i], flow_recip[i]) for i in range(12) ]
    flow_aov = [ safe_div(flow_rev[i], flow_conv[i]) for i in range(12) ]
    flow_usd_per_cust = [ safe_div(flow_rev[i], flow_recip[i]) for i in range(12) ]
    flow_share = [ safe_pct(flow_rev[i], gross_sales[i]) for i in range(12) ]
    
    return {
        "gross_sales": gross_sales,
        "total_profiles": total_profiles_history,
        "active_profiles": active_profiles,
        "active_base_growth_pct": [None]*12,
        "campaigns": {
            "open_rate_pct": camp_open_rate,
            "ctr_pct": camp_ctr,
            "conversion_rate_pct": camp_conv_rate,
            "revenue": camp_rev,
            "aov": camp_aov,
            "avg_usd_per_customer": camp_usd_per_cust,
            "recipients": camp_recip,
            "unique_opens": camp_opens,
            "share_of_total_revenue_pct": camp_share
        },
        "flows": {
            "open_rate_pct": flow_open_rate,
            "ctr_pct": flow_ctr,
            "conversion_rate_pct": flow_conv_rate,
            "revenue": flow_rev,
            "aov": flow_aov,
            "avg_usd_per_customer": flow_usd_per_cust,
            "recipients": flow_recip,
            "unique_opens": flow_opens,
            "share_of_total_revenue_pct": flow_share
        }
    }

def create_empty_bu_data():
    empty_array = [None] * 12
    return {
        "gross_sales": empty_array,
        "total_profiles": empty_array.copy(),
        "active_profiles": empty_array,
        "active_base_growth_pct": empty_array,
        "campaigns": { k: empty_array.copy() for k in ["open_rate_pct", "ctr_pct", "conversion_rate_pct", "revenue", "aov", "avg_usd_per_customer", "recipients", "unique_opens", "share_of_total_revenue_pct"] },
        "flows": { k: empty_array.copy() for k in ["open_rate_pct", "ctr_pct", "conversion_rate_pct", "revenue", "aov", "avg_usd_per_customer", "recipients", "unique_opens", "share_of_total_revenue_pct"] }
    }

def fetch_data(snapshot_closed_month=False):
    corro_key = os.environ.get("KLAVIYO_API_KEY_CORRO")
    cavali_key = os.environ.get("KLAVIYO_API_KEY_CAVALI")
    
    try:
        previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.exists() else {"bu_data": {}}
    except (OSError, json.JSONDecodeError):
        previous = {"bu_data": {}}

    result = {
        "meta": {
            "brand": "Klaviyo",
            "source": "API",
            "last_updated": date.today().isoformat(),
            "note": "Klaviyo API data. Active and total profiles are immutable snapshots captured only after each month closes.",
            "latest_closed_month_index": date.today().month - 2
        },
        "months": MONTH_LABELS,
        "bu_data": {}
    }

    for bu_name, api_key in (("CORRO", corro_key), ("Cavali Club", cavali_key)):
        result["bu_data"][bu_name] = process_bu(
            api_key, bu_name, previous.get("bu_data", {}).get(bu_name), snapshot_closed_month
        )
    
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-closed-month", action="store_true", help="Capture the previous closed month once.")
    args = parser.parse_args()
    fetch_data(snapshot_closed_month=args.snapshot_closed_month)
