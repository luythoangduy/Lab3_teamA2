from src.tools.product_tools import cheapest_in_category, refresh_cache, CATALOG

refresh_cache(30)
print("beauty products:", CATALOG.count())
payload = '{"category": "beauty"}'
print("plain beauty:", cheapest_in_category("beauty")[:200])
print("json beauty:", cheapest_in_category(payload)[:200])
