import os, requests, json

api_key = os.environ.get("KLAVIYO_API_KEY_CORRO")
headers = {
    "Authorization": f"Klaviyo-API-Key {api_key.strip() if api_key else ''}",
    "accept": "application/json",
    "revision": "2024-02-15"
}

def run():
    if not api_key: return
    # Get Received Email ID
    res = requests.get("https://a.klaviyo.com/api/metrics/?filter=equals(name,'Received Email')", headers=headers)
    metric_id = res.json()["data"][0]["id"]
    
    url = "https://a.klaviyo.com/api/campaign-values-reports/"
    payload = {
        "data": {
            "type": "campaign-values-report",
            "attributes": {
                "metric_id": metric_id,
                "interval": "month",
                "filter": "greater-or-equal(datetime,2026-01-01T00:00:00)",
                "measurements": ["unique"]
            }
        }
    }
    r = requests.post(url, json=payload, headers=headers)
    print("CAMPAIGN REPORTS:")
    print(r.status_code)
    print(r.text[:500])

run()
