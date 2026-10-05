import requests
import json

resp = requests.get("http://localhost:8000/api/approvals")
print("HTTP Status:", resp.status_code)
try:
    data = resp.json()
    print("Packages count:", len(data))
    if data:
        print(json.dumps(data[0], indent=2))
except Exception as e:
    print("Error:", e, resp.text)
