import json
import os
import sys
from datetime import date
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
            "gross_sales": 54,
            "active_profiles": 58,
            "active_base_growth_pct": 59,
            "campaigns.open_rate_pct": 61,
            "campaigns.ctr_pct": 62,
            "campaigns.conversion_rate_pct": 63,
            "campaigns.avg_usd_per_customer": 64,
            "campaigns.aov": 65,
            "campaigns.recipients": 66,
            "campaigns.unique_opens": 67,
            "campaigns.revenue": 68,
            "campaigns.share_of_total_revenue_pct": 69,
            "flows.open_rate_pct": 71,
            "flows.ctr_pct": 72,
            "flows.conversion_rate_pct": 73,
            "flows.avg_usd_per_customer": 74,
            "flows.aov": 75,
            "flows.recipients": 76,
            "flows.unique_opens": 77,
            "flows.revenue": 78,
            "flows.share_of_total_revenue_pct": 79,
        }
    }
}

MONTH_LABELS = ["ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26", "jul-26", "ago-26", "sep-26", "oct-26", "nov-26", "dic-26"]

import re

def clean_number(raw):
    if raw in (None, "", "#DIV/0!", "#REF!", "-"):
        return None
    if isinstance(raw, (int, float)):
        return raw
        
    s = str(raw).strip().replace("$", "").replace(" ", "")
    if s.endswith("%"):
        s = s.replace("%", "")
        
    multiplier = 1
    s_lower = s.lower()
    if s_lower.endswith("k"):
        multiplier = 1000
        s = s_lower.replace("k", "")
    elif s_lower.endswith("m"):
        multiplier = 1000000
        s = s_lower.replace("m", "")
        
    if re.search(r',\d{1,2}$', s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
        
    try:
        return float(s) * multiplier
    except ValueError:
        return None

def set_by_path(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value

def overlay_closed_profile_snapshots(gc, snapshot_sheet_id, result):
    """Use the dedicated immutable month-close sheet for profile population."""
    if not snapshot_sheet_id:
        return
    try:
        snapshot_book = gc.open_by_key(snapshot_sheet_id)
        try:
            records = snapshot_book.worksheet("Monthly Snapshots").get_all_records()
        except gspread.WorksheetNotFound:
            print("The dedicated snapshot sheet is ready but has no monthly snapshot yet.")
            return
    except Exception as error:
        raise RuntimeError(f"Could not read the dedicated Klaviyo snapshot sheet: {error}") from error

    for record in records:
        bu_name = str(record.get("business_unit", "")).strip()
        month = str(record.get("snapshot_month", "")).strip()
        if bu_name not in result["bu_data"] or len(month) != 7:
            continue
        try:
            month_index = int(month[5:7]) - 1
        except ValueError:
            continue
        if not 0 <= month_index < len(MONTH_LABELS):
            continue
        for field in ("active_profiles", "total_profiles"):
            value = clean_number(record.get(field))
            if value is not None:
                result["bu_data"][bu_name][field][month_index] = value

def main():
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.environ.get("SHEET_ID")
    snapshot_sheet_id = os.environ.get("KLAVIYO_SNAPSHOT_SHEET_ID")
    
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
            "latest_closed_month_index": date.today().month - 2,
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
            
        bu_result = {"total_profiles": [None] * len(MONTH_LABELS), "active_profiles": [None] * len(MONTH_LABELS)}
        for key, row in config["ROW_MAP"].items():
            start_col, end_col = config["MONTH_COLS"].split(":")
            raw_values = ws.get(f"{start_col}{row}:{end_col}{row}")
            flat = raw_values[0] if raw_values else []
            flat = flat + [None] * (len(MONTH_LABELS) - len(flat))
            cleaned = [clean_number(v) for v in flat[:len(MONTH_LABELS)]]
            set_by_path(bu_result, key, cleaned)
            
        result["bu_data"][tab_name] = bu_result

    overlay_closed_profile_snapshots(gc, snapshot_sheet_id, result)

    result["meta"]["last_updated"] = date.today().isoformat()

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"data.json actualizado con datos de CORRO y Cavali Club -> {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
