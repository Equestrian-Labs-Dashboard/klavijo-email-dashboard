import json

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

months_to_add = ['sep-26', 'oct-26', 'nov-26', 'dic-26']
data['months'].extend(months_to_add)

def pad_array(arr):
    if isinstance(arr, list):
        arr.extend([None, None, None, None])

pad_array(data['gross_sales'])
pad_array(data['active_profiles'])
pad_array(data['active_base_growth_pct'])

for key in data['campaigns']:
    pad_array(data['campaigns'][key])

for key in data['flows']:
    pad_array(data['flows'][key])

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
