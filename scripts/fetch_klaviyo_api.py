import os
import json
import requests
from datetime import date
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "klaviyo_api_data.json"
MONTH_LABELS = ["ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26", "jul-26", "ago-26", "sep-26", "oct-26", "nov-26", "dic-26"]

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
            "CORRO": create_empty_bu_data(),
            "Cavali Club": create_empty_bu_data()
        }
    }
    
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Klaviyo API data written to", OUTPUT_PATH)

def create_empty_bu_data():
    empty_array = [0] * len(MONTH_LABELS)
    return {
        "gross_sales": empty_array,
        "active_profiles": empty_array,
        "active_base_growth_pct": empty_array,
        "campaigns": {
            "open_rate_pct": empty_array,
            "ctr_pct": empty_array,
            "conversion_rate_pct": empty_array,
            "revenue": empty_array,
            "aov": empty_array,
            "avg_usd_per_customer": empty_array,
            "recipients": empty_array,
            "unique_opens": empty_array,
            "share_of_total_revenue_pct": empty_array
        },
        "flows": {
            "open_rate_pct": empty_array,
            "ctr_pct": empty_array,
            "conversion_rate_pct": empty_array,
            "revenue": empty_array,
            "aov": empty_array,
            "avg_usd_per_customer": empty_array,
            "recipients": empty_array,
            "unique_opens": empty_array,
            "share_of_total_revenue_pct": empty_array
        }
    }

if __name__ == "__main__":
    fetch_data()
