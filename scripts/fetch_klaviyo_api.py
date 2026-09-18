import os
import json
import time
import requests
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "klaviyo_api_data.json"
SHEETS_DATA_PATH = BASE_DIR / "data" / "data.json"
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
    time.sleep(1)
    return None

def fetch_aggregate(api_key, metric_id, measurement="unique", by=None, is_placed_order=False):
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
    
    primary_dim = None
    if by == "Campaign Name":
        primary_dim = "$attributed_message" if is_placed_order else "$message"
    elif by == "Flow Name":
        primary_dim = "$attributed_flow" if is_placed_order else "$message"
        
    if primary_dim:
        payload["data"]["attributes"]["by"] = [primary_dim]
        
    result_array = [None]*12
    
    for attempt in range(3):
        time.sleep(3)
        try:
            res = requests.post(url, json=payload, headers=get_headers(api_key))
            if res.status_code == 429:
                print(f"  -> Limite de velocidad (429) alcanzado. Esperando 5 segundos...")
                time.sleep(5)
                continue
            elif res.status_code == 400 and primary_dim:
                print(f"  -> ADVERTENCIA: No se puede agrupar por '{primary_dim}' en metrica {metric_id}. Intentando sin agrupar...")
                del payload["data"]["attributes"]["by"]
                primary_dim = None 
                time.sleep(4)
                continue
            elif res.status_code == 200:
                data = res.json().get("data", {}).get("attributes", {})
                dates = data.get("dates", [])
                results_data = data.get("data", [])
                if not results_data:
                    break
                    
                target_series = []
                if "by" in payload["data"]["attributes"]:
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
                            result_array[month_idx] = target_series[i] if target_series[i] else 0
                    except:
                        pass
                break
            else:
                print(f"  -> Error HTTP {res.status_code} al agrupar {metric_id}: {res.text}")
                break
        except Exception as e:
            print(f"  -> Error de Conexion ({e}). Reintentando en 5 segs...")
            time.sleep(5)
            
    current_month = date.today().month
    for i in range(current_month):
        if result_array[i] is None:
            result_array[i] = 0
            
    return result_array

def process_bu_hybrid(api_key, bu_name, sheets_bu_data):
    print(f"\n=====================================")
    print(f"PROCESANDO DATOS HIBRIDOS PARA: {bu_name}")
    print(f"=====================================")
    if not api_key:
        print(f"❌ ERROR CRITICO: La llave API para {bu_name} esta VACIA.")
        return sheets_bu_data
        
    id_placed = get_metric_id(api_key, "Placed Order")
    
    print("✅ Obteniendo Revenue Real de la API...")
    
    camp_rev = fetch_aggregate(api_key, id_placed, "sum_value", "Campaign Name", is_placed_order=True)
    flow_rev = fetch_aggregate(api_key, id_placed, "sum_value", "Flow Name", is_placed_order=True)
    
    # Gross sales as purely email revenue (API)
    gross_sales = [None]*12
    for i in range(12):
        if camp_rev[i] is not None or flow_rev[i] is not None:
            c = camp_rev[i] if camp_rev[i] is not None else 0
            f = flow_rev[i] if flow_rev[i] is not None else 0
            gross_sales[i] = c + f
            
    # Hybrid merging
    hybrid_data = json.loads(json.dumps(sheets_bu_data)) # Deep copy
    hybrid_data["gross_sales"] = gross_sales
    
    # Overwrite Revenue
    hybrid_data["campaigns"]["revenue"] = camp_rev
    hybrid_data["flows"]["revenue"] = flow_rev
    
    # Recalculate KPI metrics relying on Revenue using Sheets base volume
    def safe_div(a, b):
        return (a/b) if (a is not None and b) else 0
    def safe_pct(a, b):
        return (a/b*100) if (a is not None and b) else 0

    camp_recip = hybrid_data["campaigns"]["recipients"]
    camp_conv = hybrid_data["campaigns"]["unique_opens"] # We don't have conversions from sheets directly, wait, AOV needs conversions?
    
    # Actually, in Sheets, AOV is just calculated in the sheet. 
    # Let's approximate conversions from conversion rate
    # If Sheets has conversion_rate_pct, then conv = recip * (conv_rate_pct / 100)
    for i in range(12):
        if camp_rev[i] is not None:
            recip = camp_recip[i] if camp_recip[i] else 0
            conv_rate = hybrid_data["campaigns"]["conversion_rate_pct"][i] or 0
            convs = recip * (conv_rate / 100.0)
            hybrid_data["campaigns"]["aov"][i] = safe_div(camp_rev[i], convs)
            hybrid_data["campaigns"]["avg_usd_per_customer"][i] = safe_div(camp_rev[i], recip)
            hybrid_data["campaigns"]["share_of_total_revenue_pct"][i] = safe_pct(camp_rev[i], gross_sales[i])
            
        if flow_rev[i] is not None:
            recip = hybrid_data["flows"]["recipients"][i] if hybrid_data["flows"]["recipients"][i] else 0
            conv_rate = hybrid_data["flows"]["conversion_rate_pct"][i] or 0
            convs = recip * (conv_rate / 100.0)
            hybrid_data["flows"]["aov"][i] = safe_div(flow_rev[i], convs)
            hybrid_data["flows"]["avg_usd_per_customer"][i] = safe_div(flow_rev[i], recip)
            hybrid_data["flows"]["share_of_total_revenue_pct"][i] = safe_pct(flow_rev[i], gross_sales[i])

    return hybrid_data

def fetch_data():
    corro_key = os.environ.get("KLAVIYO_API_KEY_CORRO")
    cavali_key = os.environ.get("KLAVIYO_API_KEY_CAVALI")
    
    # Load base Sheets data for Active Profiles, Opens, CTRs
    if SHEETS_DATA_PATH.exists():
        sheets_data = json.loads(SHEETS_DATA_PATH.read_text(encoding="utf-8"))
    else:
        print("❌ Archivo de Sheets data.json no encontrado.")
        return
    
    result = {
        "meta": {
            "brand": "Klaviyo",
            "source": "API + Sheets Hibrido",
            "last_updated": date.today().isoformat(),
            "note": "Revenue extraido en vivo por API. Active Profiles y Opens mantenidos desde Sheets para evitar duplicacion."
        },
        "months": MONTH_LABELS,
        "bu_data": {
            "CORRO": process_bu_hybrid(corro_key, "CORRO", sheets_data["bu_data"].get("CORRO", {})),
            "Cavali Club": process_bu_hybrid(cavali_key, "CAVALI", sheets_data["bu_data"].get("Cavali Club", {}))
        }
    }
    
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    fetch_data()
