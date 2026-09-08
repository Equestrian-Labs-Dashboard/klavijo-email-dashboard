"""
Actualiza data/data.json leyendo la sección EMAIL MARKETING (Klaviyo) de la
hoja CORRO en Google Sheets.

Credenciales / config esperadas como VARIABLES DE ENTORNO (inyectadas por el
workflow de GitHub Actions desde GitHub Secrets, nunca hardcodeadas aquí):

  GOOGLE_SERVICE_ACCOUNT_JSON  -> contenido completo del JSON de la cuenta de
                                   servicio (con permiso de "Viewer" sobre la hoja)
  SHEET_ID                     -> el ID del spreadsheet
                                   (https://docs.google.com/spreadsheets/d/<ESTE_ID>/edit)
  SHEET_TAB                    -> nombre de la pestaña, por defecto "CORRO"

Este script NUNCA debe recibir las credenciales por argumento ni quedar
commiteado con un JSON de cuenta de servicio dentro. Ver README.md sección
"Seguridad / Secrets".
"""

import json
import os
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "data.json"

# Fila -> métrica, tal como están en la sección "EMAIL MARKETING" (Klaviyo) de
# la hoja CORRO. Ajustar si la fuente real de Klaviyo usa otra distribución.
ROW_MAP = {
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

# Columnas AT:AY = jan-26 .. aug-26 en la hoja de referencia. Actualizar el
# rango a medida que avancen los meses.
MONTH_COLS = "AT:AY"
MONTH_LABELS = ["ene-26", "feb-26", "mar-26", "abr-26", "may-26", "jun-26", "jul-26", "ago-26"]


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
    sheet_tab = os.environ.get("SHEET_TAB", "CORRO")

    if not creds_json or not sheet_id:
        print("Faltan GOOGLE_SERVICE_ACCOUNT_JSON o SHEET_ID en el entorno.", file=sys.stderr)
        sys.exit(1)

    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(sheet_tab)

    result = {
        "meta": {
            "brand": "Klaviyo",
            "source": "Klaviyo",
            "last_updated": None,
            "note": "Actualizado automáticamente desde Google Sheets vía GitHub Actions.",
        },
        "months": MONTH_LABELS,
    }

    for key, row in ROW_MAP.items():
        raw_values = ws.get(f"{MONTH_COLS.split(':')[0]}{row}:{MONTH_COLS.split(':')[1]}{row}")
        flat = raw_values[0] if raw_values else []
        # pad to expected length
        flat = flat + [None] * (len(MONTH_LABELS) - len(flat))
        cleaned = [clean_number(v) for v in flat[: len(MONTH_LABELS)]]
        set_by_path(result, key, cleaned)

    from datetime import date
    result["meta"]["last_updated"] = date.today().isoformat()

    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"data.json actualizado con datos de {sheet_tab} -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
