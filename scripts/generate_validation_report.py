"""Create the API vs. Google Sheet reconciliation report committed with each refresh."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET_PATH = ROOT / "data" / "data.json"
API_PATH = ROOT / "data" / "klaviyo_api_data.json"
REPORT_PATH = ROOT / "reports" / "klaviyo_validation_report.md"


def value_at(data, path, index):
    current = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current[index] if isinstance(current, list) and index < len(current) else None


def revenue_at(data, index):
    campaign = value_at(data, "campaigns.revenue", index)
    flows = value_at(data, "flows.revenue", index)
    return None if campaign is None and flows is None else (campaign or 0) + (flows or 0)


def fmt(value):
    return "—" if value is None else f"{value:,.2f}".rstrip("0").rstrip(".")


def compare(api_value, sheet_value):
    if api_value is None or sheet_value is None:
        return "No comparable"
    return fmt(api_value - sheet_value)


def is_invalid_zero_export(bu):
    values = []
    for path in ("gross_sales", "campaigns.revenue", "flows.revenue", "active_profiles"):
        current = bu
        for key in path.split("."):
            current = current.get(key, {}) if isinstance(current, dict) else []
        if isinstance(current, list):
            values.extend(value for value in current if isinstance(value, (int, float)))
    return bool(values) and all(value == 0 for value in values)


def main():
    sheet = json.loads(SHEET_PATH.read_text(encoding="utf-8"))
    api = json.loads(API_PATH.read_text(encoding="utf-8"))
    months = sheet.get("months", [])
    lines = [
        "# Reporte de conciliación — Klaviyo",
        "",
        f"Generado: {date.today().isoformat()}",
        "",
        "La API aporta datos actuales. Google Sheet es el histórico consolidado."
        " `No comparable` significa que una fuente no entregó el KPI; nunca equivale a cero.",
        "",
    ]
    metrics = [
        ("Gross Sales", lambda d, i: value_at(d, "gross_sales", i)),
        ("Revenue", revenue_at),
        ("Campaign Revenue", lambda d, i: value_at(d, "campaigns.revenue", i)),
        ("Profiles", lambda d, i: value_at(d, "total_profiles", i)),
        ("Active Profiles", lambda d, i: value_at(d, "active_profiles", i)),
    ]
    for bu_name in sorted(set(sheet.get("bu_data", {})) | set(api.get("bu_data", {}))):
        lines.extend([f"## {bu_name}", ""])
        sheet_bu = sheet.get("bu_data", {}).get(bu_name, {})
        api_bu = api.get("bu_data", {}).get(bu_name, {})
        if is_invalid_zero_export(api_bu):
            lines.extend(["**Estado API:** extracción inválida (todos los KPIs son cero). Se requiere ejecutar el workflow con secretos válidos.", ""])
            api_bu = {}
        for idx, month in enumerate(months):
            rows = []
            for name, getter in metrics:
                api_value, sheet_value = getter(api_bu, idx), getter(sheet_bu, idx)
                if api_value is not None or sheet_value is not None:
                    rows.append((name, api_value, sheet_value))
            if not rows:
                continue
            lines.extend([f"### {month}", "", "| KPI | API | Google Sheet | Diferencia (API - Sheet) |", "| --- | ---: | ---: | ---: |"])
            lines.extend(f"| {name} | {fmt(a)} | {fmt(s)} | {compare(a, s)} |" for name, a, s in rows)
            lines.append("")
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
