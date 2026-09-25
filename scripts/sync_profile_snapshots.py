"""Write immutable Klaviyo profile snapshots to a dedicated Google Sheet."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parent.parent
API_PATH = ROOT / "data" / "klaviyo_api_data.json"
SHEET_TAB = "Monthly Snapshots"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main():
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    snapshot_sheet_id = os.environ.get("KLAVIYO_SNAPSHOT_SHEET_ID")
    if not service_account_json or not snapshot_sheet_id:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON or KLAVIYO_SNAPSHOT_SHEET_ID.")

    data = json.loads(API_PATH.read_text(encoding="utf-8"))
    closed_index = data.get("meta", {}).get("latest_closed_month_index")
    months = data.get("months", [])
    if not isinstance(closed_index, int) or not 0 <= closed_index < len(months):
        print("No closed month is available yet; no profile snapshot was written.")
        return

    credentials = Credentials.from_service_account_info(json.loads(service_account_json), scopes=SCOPES)
    workbook = gspread.authorize(credentials).open_by_key(snapshot_sheet_id)
    try:
        worksheet = workbook.worksheet(SHEET_TAB)
    except gspread.WorksheetNotFound:
        worksheet = workbook.add_worksheet(title=SHEET_TAB, rows=200, cols=8)
        worksheet.append_row(["snapshot_month", "business_unit", "active_profiles", "total_profiles", "source", "captured_at_utc", "status", "notes"])
        worksheet.freeze(rows=1)

    records = worksheet.get_all_records()
    existing = {(str(row.get("snapshot_month")), str(row.get("business_unit"))) for row in records}
    year = datetime.now(timezone.utc).year
    snapshot_month = f"{year}-{closed_index + 1:02d}"
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = []

    for bu_name, bu_data in data.get("bu_data", {}).items():
        if (snapshot_month, bu_name) in existing:
            print(f"Keeping existing immutable snapshot: {snapshot_month} / {bu_name}")
            continue
        active = bu_data.get("active_profiles", [None] * 12)[closed_index]
        total = bu_data.get("total_profiles", [None] * 12)[closed_index]
        if active is None and total is None:
            print(f"No profile values available for {snapshot_month} / {bu_name}; skipped.")
            continue
        rows.append([snapshot_month, bu_name, active, total, "Klaviyo API", captured_at, "Closed", "Immutable month-close snapshot"])

    if rows:
        worksheet.append_rows(rows, value_input_option="RAW")
        print(f"Wrote {len(rows)} closed-month snapshot row(s) to the dedicated Klaviyo sheet.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
