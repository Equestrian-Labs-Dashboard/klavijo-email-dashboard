import os
import json
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

def get_metric_id(api_key, name):
    url = "https://a.klaviyo.com/api/metrics/"
    print(f"Buscando metrica: {name}...")
    try:
        res = requests.get(url, headers=get_headers(api_key))
        if res.status_code == 200:
            data = res.json().get("data", [])
            for item in data:
                metric_name = item.get("attributes", {}).get("name", "")
                if metric_name.lower() == name.lower():
                    print(f"  -> EXITO: ID encontrado = {item['id']} para {metric_name}")
                    return item["id"]
            print(f"  -> ADVERTENCIA: No se encontro '{name}' en la cuenta.")
        else:
            print(f"  -> ERROR de Klaviyo ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"  -> ERROR de red: {e}")
    return None

def fetch_aggregate(api_key, metric_id, measurement="unique", by=None):
    if not metric_id: return [0]*12
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
    if by:
        payload["data"]["attributes"]["by"] = [by]
        
    result_array = [0]*12
    try:
        res = requests.post(url, json=payload, headers=get_headers(api_key))
        if res.status_code == 200:
            data = res.json().get("data", {}).get("attributes", {})
            dates = data.get("dates", [])
            results_data = data.get("data", [])
            
            if not results_data:
                return result_array
                
            target_series = []
            if by:
                sums = [0]*len(dates)
                for group in results_data:
                    dim_val = group.get("dimensions", [])
                    if dim_val and dim_val[0]:
                        vals = group.get("measurements", {}).get(measurement, [])
                        for i, v in enumerate(vals):
                            sums[i] += v
                target_series = sums
            else:
                target_series = results_data[0].get("measurements", {}).get(measurement, [])
                
            for i, d in enumerate(dates):
                try:
                    month_idx = int(d[5:7]) - 1
                    if 0 <= month_idx < 12 and i < len(target_series):
                        result_array[month_idx] = target_series[i]
                except:
                    pass
        else:
            print(f"Error HTTP {res.status_code} al agrupar {metric_id}: {res.text}")
    except Exception as e:
        print(f"Exception al agrupar {metric_id}: {e}")
        
    return result_array

def process_bu(api_key, bu_name):
    print(f"\n=====================================")
    print(f"PROCESANDO DATOS PARA: {bu_name}")
    print(f"=====================================")
    if not api_key:
        print(f"❌ ERROR CRITICO: La llave API para {bu_name} esta VACIA o es NULA.")
        return create_empty_bu_data()
        
    print(f"✅ Llave detectada. Verificando permisos y metricas...")
    
    id_placed = get_metric_id(api_key, "Placed Order")
    id_received = get_metric_id(api_key, "Received Email")
    id_opened = get_metric_id(api_key, "Opened Email")
    id_clicked = get_metric_id(api_key, "Clicked Email")
    
    if not id_placed and not id_received and not id_opened:
        print(f"⚠️ PELIGRO: No se encontraron los IDs. Esto puede pasar si las metricas estan en espanol o falta permiso de lectura en la API Key.")
    else:
        print("✅ Empezando a descargar los totales...")
    
    gross_sales = fetch_aggregate(api_key, id_placed, "sum_value")
    
    camp_rev = fetch_aggregate(api_key, id_placed, "sum_value", "$campaign")
    camp_conv = fetch_aggregate(api_key, id_placed, "unique", "$campaign")
    camp_recip = fetch_aggregate(api_key, id_received, "unique", "$campaign")
    camp_opens = fetch_aggregate(api_key, id_opened, "unique", "$campaign")
    camp_clicks = fetch_aggregate(api_key, id_clicked, "unique", "$campaign")
    
    flow_rev = fetch_aggregate(api_key, id_placed, "sum_value", "$flow")
    flow_conv = fetch_aggregate(api_key, id_placed, "unique", "$flow")
    flow_recip = fetch_aggregate(api_key, id_received, "unique", "$flow")
    flow_opens = fetch_aggregate(api_key, id_opened, "unique", "$flow")
    flow_clicks = fetch_aggregate(api_key, id_clicked, "unique", "$flow")
    
    camp_open_rate = [ (camp_opens[i]/camp_recip[i]*100) if camp_recip[i] else 0 for i in range(12) ]
    camp_ctr = [ (camp_clicks[i]/camp_opens[i]*100) if camp_opens[i] else 0 for i in range(12) ]
    camp_conv_rate = [ (camp_conv[i]/camp_recip[i]*100) if camp_recip[i] else 0 for i in range(12) ]
    camp_aov = [ (camp_rev[i]/camp_conv[i]) if camp_conv[i] else 0 for i in range(12) ]
    camp_usd_per_cust = [ (camp_rev[i]/camp_recip[i]) if camp_recip[i] else 0 for i in range(12) ]
    camp_share = [ (camp_rev[i]/gross_sales[i]*100) if gross_sales[i] else 0 for i in range(12) ]
    
    flow_open_rate = [ (flow_opens[i]/flow_recip[i]*100) if flow_recip[i] else 0 for i in range(12) ]
    flow_ctr = [ (flow_clicks[i]/flow_opens[i]*100) if flow_opens[i] else 0 for i in range(12) ]
    flow_conv_rate = [ (flow_conv[i]/flow_recip[i]*100) if flow_recip[i] else 0 for i in range(12) ]
    flow_aov = [ (flow_rev[i]/flow_conv[i]) if flow_conv[i] else 0 for i in range(12) ]
    flow_usd_per_cust = [ (flow_rev[i]/flow_recip[i]) if flow_recip[i] else 0 for i in range(12) ]
    flow_share = [ (flow_rev[i]/gross_sales[i]*100) if gross_sales[i] else 0 for i in range(12) ]
    
    return {
        "gross_sales": gross_sales,
        "active_profiles": [0]*12,
        "active_base_growth_pct": [0]*12,
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
    empty_array = [0] * len(MONTH_LABELS)
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
            "source": "Klaviyo API",
            "last_updated": date.today().isoformat(),
            "note": "Datos obtenidos por API."
        },
        "months": MONTH_LABELS,
        "bu_data": {
            "CORRO": process_bu(corro_key, "CORRO"),
            "Cavali Club": process_bu(cavali_key, "CAVALI")
        }
    }
    
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n-------------------------------------")
    print("Klaviyo API data written to", OUTPUT_PATH)
    print("-------------------------------------")

if __name__ == "__main__":
    fetch_data()
