import json
import os
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "data.json"

TABS = {
    "CORRO": {
        "MONTH_COLS": "AT:BE",
        "ROW_MAP": {
            "gross_sales": 43,
            "active_profiles": 47,
            "active_base_growth_pct": 48,
            "campaigns.open_rate_pct": 50,
            "campaigns.ctr_pct": 51,
            "campaigns.conversion_rate_pct": 52,
            "campaigns.avg_usd_per_customer": 53,
            "campaigns.aov": 54,
            "campaigns.recipients": 55,
            "campaigns.unique_opens": 56,
            "campaigns.revenue": 57,
            "campaigns.share_of_total_revenue_pct": 58,
            "flows.open_rate_pct": 60,
            "flows.ctr_pct": 61,
            "flows.conversion_rate_pct": 62,
            "flows.avg_usd_per_customer": 63,
            "flows.aov": 64,
            "flows.recipients": 65,
            "flows.unique_opens": 66,
            "flows.revenue": 67,
            "flows.share_of_total_revenue_pct": 68,
        }
    },
    "Cavali Club": {
        "MONTH_COLS": "Z:AK",
        "ROW_MAP": {
            "gross_sales": 52,
            "active_profiles": 56,
            "active_base_growth_pct": 57,
            "campaigns.open_rate_pct": 59,
            "campaigns.ctr_pct": 60,
            "campaigns.conversion_rate_pct": 61,
            "campaigns.avg_usd_per_customer": 62,
            "campaigns.aov": 63,
            "campaigns.recipients": 64,
            "campaigns.unique_opens": 65,
            "campaigns.revenue": 66,
            "campaigns.share_of_total_revenue_pct": 67,
            "flows.open_rate_pct": 69,
            "flows.ctr_pct": 70,
            "flows.conversion_rate_pct": 71,
            "flows.avg_usd_per_customer": 72,
            "flows.aov": 73,
            "flows.recipients": 74,
            "flows.unique_opens": 75,
            "flows.revenue": 76,
            "flows.share_of_total_revenue_pct": 77,
        }
    }
}

MONTH_LABELS = ["ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26", "jul-26", "ago-26", "sep-26", "oct-26", "nov-26", "dic-26"]

def clean_number(raw):
    if raw in (None, "", "#DIV/0!", "#REF!"):
        return None
    if isinstance(raw, (int, float)):
        return raw
    s = str(raw).replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def set_by_path(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value

def main():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    
    if not creds_json or not sheet_id:
        print("Faltan GOOGLE_SERVICE_ACCOUNT_JSON o SHEET_ID en el entorno.", file=sys.stderr)
        sys.exit(1)

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)

    result = {
        "meta": {
            "brand": "Klaviyo",
            "source": "Klaviyo",
            "last_updated": None,
            "note": "Actualizado automáticamente desde Google Sheets vía GitHub Actions.",
        },
        "months": MONTH_LABELS,
        "bu_data": {}
    }

    for tab_name, config in TABS.items():
        try:
            ws = sh.worksheet(tab_name)
        except Exception as e:
            print(f"Error cargando tab {tab_name}: {e}")
            continue
            
        bu_result = {}
        for key, row in config["ROW_MAP"].items():
            start_col, end_col = config["MONTH_COLS"].split(":")
            raw_values = ws.get(f"{start_col}{row}:{end_col}{row}")
            flat = raw_values[0] if raw_values else []
            flat = flat + [None] * (len(MONTH_LABELS) - len(flat))
            cleaned = [clean_number(v) for v in flat[:len(MONTH_LABELS)]]
            set_by_path(bu_result, key, cleaned)
            
        result["bu_data"][tab_name] = bu_result

    from datetime import date
    result["meta"]["last_updated"] = date.today().isoformat()

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"data.json actualizado con datos de CORRO y Cavali Club -> {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
