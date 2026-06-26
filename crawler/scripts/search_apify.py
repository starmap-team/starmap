import httpx
import os
os.environ['NO_PROXY'] = '*'

token = os.environ.get("APIFY_TOKEN", "")
headers = {'Authorization': f'Bearer {token}'}

# 51job
r = httpx.get('https://api.apify.com/v2/store?search=51job&limit=10', headers=headers, timeout=30)
items = r.json().get('data', {}).get('items', [])
print('=== 51job ===')
for x in items:
    print(f'  {x.get("name", "?")} (runs: {x.get("stats", {}).get("totalRuns", 0)})')

# zhipin
r2 = httpx.get('https://api.apify.com/v2/store?search=zhipin&limit=10', headers=headers, timeout=30)
items2 = r2.json().get('data', {}).get('items', [])
print('\n=== Zhipin ===')
for x in items2:
    print(f'  {x.get("name", "?")} (runs: {x.get("stats", {}).get("totalRuns", 0)})')

# liepin
r3 = httpx.get('https://api.apify.com/v2/store?search=liepin&limit=10', headers=headers, timeout=30)
items3 = r3.json().get('data', {}).get('items', [])
print('\n=== Liepin ===')
for x in items3:
    print(f'  {x.get("name", "?")} (runs: {x.get("stats", {}).get("totalRuns", 0)})')
