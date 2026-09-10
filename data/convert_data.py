import json

with open('data.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)

new_data = {
    "meta": old_data.get("meta", {}),
    "months": old_data.get("months", []),
    "bu_data": {
        "CORRO": {},
        "Cavali Club": {}
    }
}

for key in ["gross_sales", "active_profiles", "active_base_growth_pct", "campaigns", "flows"]:
    if key in old_data:
        new_data["bu_data"]["CORRO"][key] = old_data[key]
        new_data["bu_data"]["Cavali Club"][key] = old_data[key]

# Keep gross_sales_2025 in both (or just CORRO if they only had it there)
if "gross_sales_2025" in old_data:
    new_data["bu_data"]["CORRO"]["gross_sales_2025"] = old_data["gross_sales_2025"]
    new_data["bu_data"]["Cavali Club"]["gross_sales_2025"] = old_data["gross_sales_2025"]

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(new_data, f, indent=2, ensure_ascii=False)
