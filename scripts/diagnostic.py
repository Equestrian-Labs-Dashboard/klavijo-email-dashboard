import os
import requests
import json

def run():
    api_key = os.environ.get("KLAVIYO_API_KEY_CORRO")
    if not api_key: return
    headers = {
        "Authorization": f"Klaviyo-API-Key {api_key.strip()}",
        "accept": "application/json",
        "revision": "2024-02-15"
    }
    
    res = requests.get("https://a.klaviyo.com/api/metrics/?filter=equals(name,'Received Email')", headers=headers)
    try:
        metric_id = res.json()["data"][0]["id"]
    except:
        return
        
    print(f"Testing metric: {metric_id}")
    res2 = requests.get(f"https://a.klaviyo.com/api/metrics/{metric_id}/", headers=headers)
    print("METRIC DETAILS:")
    print(json.dumps(res2.json(), indent=2))

run()
