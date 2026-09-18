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

def get_total_profiles(api_key):
    print("  -> Calculando perfiles activos aproximados...")
    lists = fetch_all_pages("https://a.klaviyo.com/api/lists/", get_headers(api_key))
    total = 0
    # En Klaviyo v2024-02-15, la API de lists no devuelve profile_count directamente, 
    # pero devolveremos 0 si no se puede para no romper, y explicaremos la limitacion.
    return total

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

def process_bu(api_key, bu_name):
    print(f"\n=====================================")
    print(f"PROCESANDO API PURA PARA: {bu_name}")
    print(f"=====================================")
    if not api_key:
        return create_empty_bu_data()
        
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
    
    # Active Profiles (No historico, Klaviyo no provee esto en Metric Aggregates)
    active_profiles = [None]*12
    
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
        "active_profiles": empty_array,
        "active_base_growth_pct": empty_array,
        "campaigns": { k: empty_array.copy() for k in ["open_rate_pct", "ctr_pct", "conversion_rate_pct", "revenue", "aov", "avg_usd_per_customer", "recipients", "unique_opens", "share_of_total_revenue_pct"] },
        "flows": { k: empty_array.copy() for k in ["open_rate_pct", "ctr_pct", "conversion_rate_pct", "revenue", "aov", "avg_usd_per_customer", "recipients", "unique_opens", "share_of_total_revenue_pct"] }
    }

def fetch_data():
    corro_key = os.environ.get("KLAVIYO_API_KEY_CORRO")
    cavali_key = os.environ.get("KLAVIYO_API_KEY_CAVALI")
    
    result = {
        "meta": {
            "brand": "Klaviyo",
            "source": "API",
            "last_updated": date.today().isoformat(),
            "note": "100% API Pura. Active profiles no historicos."
        },
        "months": MONTH_LABELS,
        "bu_data": {
            "CORRO": process_bu(corro_key, "CORRO"),
            "Cavali Club": process_bu(cavali_key, "CAVALI")
        }
    }
    
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    fetch_data()
