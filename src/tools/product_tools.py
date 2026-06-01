"""
Product catalog tools backed by https://dummyjson.com/products
"""
import json
import os
from typing import Any, Callable, Dict, List, Optional

import requests

API_BASE = "https://dummyjson.com"
CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "products_cache.json",
)


def _fetch_json(url: str, params: Optional[dict] = None) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        return {"error": str(exc), "products": []}


def _load_cache() -> List[dict]:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("products", data if isinstance(data, list) else [])
    return []


def _save_cache(products: List[dict]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"products": products}, f, indent=2)


def refresh_cache(limit: int = 100) -> str:
    """Download products into local cache for offline demos."""
    data = _fetch_json(f"{API_BASE}/products", {"limit": limit})
    products = data.get("products", [])
    if products:
        _save_cache(products)
        return f"Cached {len(products)} products to {CACHE_PATH}"
    return f"Cache refresh failed: {data.get('error', 'no products')}"


def search_products(query: str) -> str:
    """Search products by title/description. Arg: query (string)."""
    data = _fetch_json(f"{API_BASE}/products/search", {"q": query})
    if "error" in data and not data.get("products"):
        products = [
            p
            for p in _load_cache()
            if query.lower() in p.get("title", "").lower()
            or query.lower() in p.get("category", "").lower()
        ]
        if not products:
            return json.dumps({"total": 0, "products": [], "note": "offline cache, no matches"})
        return json.dumps({"total": len(products), "products": _summarize(products[:10])})

    products = data.get("products", [])
    return json.dumps(
        {"total": data.get("total", len(products)), "products": _summarize(products[:10])}
    )


def get_product_by_id(product_id: int) -> str:
    """Get one product by numeric id. Arg: product_id (int)."""
    data = _fetch_json(f"{API_BASE}/products/{product_id}")
    if "error" in data or not data.get("id"):
        for p in _load_cache():
            if p.get("id") == product_id:
                return json.dumps(_summarize([p])[0])
        return json.dumps({"error": f"Product id {product_id} not found"})
    return json.dumps(_summarize([data])[0])


def list_by_category(category: str) -> str:
    """List products in a category (beauty, fragrances, furniture, groceries, ...)."""
    data = _fetch_json(f"{API_BASE}/products/category/{category}")
    products = data.get("products", [])
    if not products:
        products = [p for p in _load_cache() if p.get("category", "").lower() == category.lower()]
    return json.dumps({"category": category, "count": len(products), "products": _summarize(products[:15])})


def cheapest_in_category(category: str) -> str:
    """Find lowest-price in-stock item in a category. Arg: category (string)."""
    raw = list_by_category(category)
    data = json.loads(raw)
    products = data.get("products", [])
    if not products:
        return json.dumps({"error": f"No products in category '{category}'"})
    cheapest = min(products, key=lambda p: p["price"])
    return json.dumps(cheapest)


def _summarize(products: List[dict]) -> List[dict]:
    out = []
    for p in products:
        out.append(
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "category": p.get("category"),
                "price": p.get("price"),
                "stock": p.get("stock"),
                "rating": p.get("rating"),
                "brand": p.get("brand"),
                "availabilityStatus": p.get("availabilityStatus"),
            }
        )
    return out


_TOOL_FUNCS: Dict[str, Callable[..., str]] = {
    "search_products": search_products,
    "get_product_by_id": get_product_by_id,
    "list_by_category": list_by_category,
    "cheapest_in_category": cheapest_in_category,
}

PRODUCT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_products",
        "description": "Search catalog by keyword (title, brand, category). Args: query (string)",
        "func": search_products,
    },
    {
        "name": "get_product_by_id",
        "description": "Fetch exact product by id. Args: product_id (integer)",
        "func": get_product_by_id,
    },
    {
        "name": "list_by_category",
        "description": "List products in category: beauty, fragrances, furniture, groceries, etc. Args: category (string)",
        "func": list_by_category,
    },
    {
        "name": "cheapest_in_category",
        "description": "Return the cheapest product in a category. Args: category (string)",
        "func": cheapest_in_category,
    },
]


def execute_tool(tool_name: str, args: str) -> str:
    if tool_name not in _TOOL_FUNCS:
        return json.dumps({"error": "HALLUCINATED_TOOL", "message": f"Tool '{tool_name}' does not exist"})

    fn = _TOOL_FUNCS[tool_name]
    arg = args.strip().strip('"').strip("'")

    try:
        if tool_name == "get_product_by_id":
            return fn(int(arg))
        return fn(arg)
    except (ValueError, TypeError) as exc:
        return json.dumps({"error": "INVALID_ARGS", "message": str(exc), "received": args})
