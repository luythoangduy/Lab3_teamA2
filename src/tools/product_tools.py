import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import requests


DUMMYJSON_PRODUCTS_URL = "https://dummyjson.com/products"
DEFAULT_DB_PATH = Path("data/products.sqlite3")


class ProductCatalog:
    """Small SQLite-backed product catalog loaded from DummyJSON."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        api_url: str = DUMMYJSON_PRODUCTS_URL,
        request_timeout: int = 15,
    ):
        self.db_path = Path(db_path)
        self.api_url = api_url
        self.request_timeout = request_timeout
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    price REAL,
                    discount_percentage REAL,
                    rating REAL,
                    stock INTEGER,
                    brand TEXT,
                    sku TEXT,
                    thumbnail TEXT,
                    images TEXT,
                    tags TEXT
                )
                """
            )

    def count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM products").fetchone()[0])

    def refresh_from_api(self, limit: int = 100) -> int:
        response = requests.get(self.api_url, params={"limit": limit}, timeout=self.request_timeout)
        response.raise_for_status()
        products = response.json().get("products", [])

        with self._connect() as conn:
            conn.execute("DELETE FROM products")
            conn.executemany(
                """
                INSERT INTO products (
                    id, title, description, category, price, discount_percentage,
                    rating, stock, brand, sku, thumbnail, images, tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._to_row(product) for product in products],
            )
        return len(products)

    def ensure_loaded(self) -> int:
        if self.count() == 0:
            return self.refresh_from_api()
        return self.count()

    def search_products(self, user_query: str, limit: int = 5) -> List[Dict[str, Any]]:
        self.ensure_loaded()
        limit = self._safe_limit(limit)
        terms = self._heuristic_terms(user_query)

        if not terms:
            sql = "SELECT * FROM products ORDER BY rating DESC, stock DESC LIMIT ?"
            params: Sequence[Any] = (limit,)
        else:
            searchable_columns = ["title", "description", "category", "brand", "tags"]
            clauses = []
            params = []
            for term in terms:
                like_group = " OR ".join([f"LOWER({col}) LIKE ?" for col in searchable_columns])
                clauses.append(f"({like_group})")
                params.extend([f"%{term}%"] * len(searchable_columns))

            sql = f"""
                SELECT *
                FROM products
                WHERE {" OR ".join(clauses)}
                ORDER BY rating DESC, discount_percentage DESC, stock DESC
                LIMIT ?
            """
            params.append(limit)

        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def query_sql(self, sql: str, limit: int = 5) -> List[Dict[str, Any]]:
        self.ensure_loaded()
        normalized = sql.strip().rstrip(";")
        if not re.match(r"(?is)^select\b", normalized):
            raise ValueError("Only SELECT queries are allowed.")
        if re.search(r"(?is)\b(insert|update|delete|drop|alter|create|replace|truncate)\b", normalized):
            raise ValueError("Write or schema-changing SQL is not allowed.")

        if not re.search(r"(?is)\blimit\b", normalized):
            normalized = f"{normalized} LIMIT {self._safe_limit(limit)}"

        with self._connect() as conn:
            return [dict(row) for row in conn.execute(normalized).fetchall()]

    def format_products_markdown(self, products: Iterable[Dict[str, Any]], limit: int = 5) -> str:
        rows = list(products)[: self._safe_limit(limit)]
        if not rows:
            return "No matching products found."

        blocks = []
        for idx, product in enumerate(rows, start=1):
            title = product.get("title", "Unknown product")
            price = product.get("price", "N/A")
            category = product.get("category", "unknown")
            rating = product.get("rating", "N/A")
            stock = product.get("stock", "N/A")
            image = product.get("thumbnail") or self._first_image(product)
            image_line = f"![{title}]({image})\n" if image else ""
            blocks.append(
                f"{idx}. **{title}**\n"
                f"{image_line}"
                f"- Price: ${price}\n"
                f"- Category: {category}\n"
                f"- Rating: {rating} | Stock: {stock}"
            )
        return "\n\n".join(blocks)

    def search_markdown(self, user_query: str, limit: int = 5) -> str:
        return self.format_products_markdown(self.search_products(user_query, limit), limit)

    def sql_markdown(self, sql: str, limit: int = 5) -> str:
        return self.format_products_markdown(self.query_sql(sql, limit), limit)

    @staticmethod
    def _safe_limit(limit: int) -> int:
        return max(1, min(int(limit), 5))

    @staticmethod
    def _to_row(product: Dict[str, Any]) -> tuple:
        dimensions = product.get("dimensions") or {}
        metadata_tags = product.get("tags") or []
        tags = metadata_tags + [
            str(product.get("warrantyInformation", "")),
            str(product.get("shippingInformation", "")),
            json.dumps(dimensions),
        ]
        return (
            product.get("id"),
            product.get("title", ""),
            product.get("description", ""),
            product.get("category", ""),
            product.get("price"),
            product.get("discountPercentage"),
            product.get("rating"),
            product.get("stock"),
            product.get("brand", ""),
            product.get("sku", ""),
            product.get("thumbnail", ""),
            json.dumps(product.get("images", [])),
            json.dumps(tags),
        )

    @staticmethod
    def _first_image(product: Dict[str, Any]) -> Optional[str]:
        raw_images = product.get("images")
        if isinstance(raw_images, str):
            try:
                raw_images = json.loads(raw_images)
            except json.JSONDecodeError:
                return None
        if raw_images:
            return raw_images[0]
        return None

    @staticmethod
    def _heuristic_terms(user_query: str) -> List[str]:
        text = user_query.lower()
        terms = re.findall(r"[a-z0-9]+", text)
        heuristic_map = {
            ("looks young", "young", "teen", "fresh", "cute", "bright color", "bright"): [
                "white",
                "yellow",
                "pink",
                "blue",
                "red",
                "top",
                "dress",
            ],
            ("garment", "clothes", "clothing", "fashion", "wear", "outfit"): [
                "top",
                "shirt",
                "dress",
                "shoe",
                "bag",
                "jewel",
                "watch",
            ],
            ("woman", "women", "female", "lady", "girl"): ["women", "womens", "dress", "beauty", "jewel"],
            ("man", "men", "male", "boy"): ["men", "mens", "shirt", "shoe", "watch"],
            ("cheap", "budget", "low price", "affordable"): ["discount", "sale"],
        }

        for triggers, expansions in heuristic_map.items():
            if any(trigger in text for trigger in triggers):
                terms.extend(expansions)

        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "for",
            "from",
            "i",
            "me",
            "of",
            "on",
            "please",
            "show",
            "the",
            "to",
            "want",
            "with",
        }
        unique_terms = []
        for term in terms:
            if term not in stop_words and term not in unique_terms:
                unique_terms.append(term)
        return unique_terms[:12]


CATALOG = ProductCatalog()


def refresh_cache(limit: int = 100) -> str:
    count = CATALOG.refresh_from_api(limit=limit)
    return f"Cached {count} products to {CATALOG.db_path}"


def search_products(args: str) -> str:
    query, limit = _parse_query_and_limit(args)
    return CATALOG.search_markdown(query, limit)


def query_products_sql(args: str) -> str:
    payload = _parse_args(args)
    if isinstance(payload, dict):
        sql = payload.get("sql") or payload.get("query") or ""
        limit = int(payload.get("limit", 5))
    else:
        sql = str(payload)
        limit = 5
    return CATALOG.sql_markdown(sql, limit)


def _parse_category(args: str) -> str:
    payload = _parse_args(args)
    if isinstance(payload, dict):
        return str(payload.get("category", payload.get("query", ""))).strip()
    return str(payload).strip().strip("\"'")


def list_by_category(args: str) -> str:
    category = _parse_category(args)
    sql = "SELECT * FROM products WHERE LOWER(category) = LOWER(?) ORDER BY rating DESC LIMIT ?"
    CATALOG.ensure_loaded()
    with CATALOG._connect() as conn:
        rows = [dict(row) for row in conn.execute(sql, (category, 5)).fetchall()]
    return CATALOG.format_products_markdown(rows, 5)


def get_product_by_id(args: str) -> str:
    payload = _parse_args(args)
    if isinstance(payload, dict):
        product_id = int(payload.get("product_id", payload.get("id", 0)))
    else:
        product_id = int(str(payload).strip().strip('"\''))
    CATALOG.ensure_loaded()
    with CATALOG._connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not row:
        return json.dumps({"error": f"Product id {product_id} not found"})
    return CATALOG.format_products_markdown([dict(row)], 1)


def cheapest_in_category(args: str) -> str:
    category = _parse_category(args)
    if not category:
        return json.dumps({"error": "INVALID_ARGS", "message": "category is required"})
    CATALOG.ensure_loaded()
    with CATALOG._connect() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT * FROM products
                WHERE LOWER(category) = LOWER(?)
                ORDER BY price ASC
                LIMIT 1
                """,
                (category,),
            ).fetchall()
        ]
    return CATALOG.format_products_markdown(rows, 1)


def create_product_tools(catalog: Optional[ProductCatalog] = None) -> List[Dict[str, Any]]:
    active_catalog = catalog or CATALOG

    def refresh_products_tool(args: str = "") -> str:
        count = active_catalog.refresh_from_api()
        return f"Loaded {count} products from DummyJSON."

    def search_products_tool(args: str) -> str:
        query, limit = _parse_query_and_limit(args)
        return active_catalog.search_markdown(query, limit)

    def query_products_sql_tool(args: str) -> str:
        payload = _parse_args(args)
        if isinstance(payload, dict):
            sql = payload.get("sql") or payload.get("query") or ""
            limit = int(payload.get("limit", 5))
        else:
            sql = str(payload)
            limit = 5
        return active_catalog.sql_markdown(sql, limit)

    def get_product_by_id_tool(args: str) -> str:
        return get_product_by_id(args)

    def cheapest_in_category_tool(args: str) -> str:
        return cheapest_in_category(args)

    def list_by_category_tool(args: str) -> str:
        return list_by_category(args)

    return [
        {
            "name": "refresh_products",
            "description": "Load or refresh product data from https://dummyjson.com/products into local SQLite.",
            "function": refresh_products_tool,
        },
        {
            "name": "search_products",
            "description": (
                "Search products using natural language and heuristics. "
                "Useful for requests like looks young, bright color, garment for woman, or product names. "
                "Returns at most 5 products with Markdown images."
            ),
            "function": search_products_tool,
        },
        {
            "name": "query_products_sql",
            "description": (
                "Run a read-only SELECT query against the products SQLite table. "
                "Columns include id, title, description, category, price, rating, stock, brand, thumbnail, images, tags."
            ),
            "function": query_products_sql_tool,
        },
        {
            "name": "get_product_by_id",
            "description": 'Fetch product by id. Example: get_product_by_id({"product_id": 7})',
            "function": get_product_by_id_tool,
        },
        {
            "name": "cheapest_in_category",
            "description": 'Cheapest in category. Example: cheapest_in_category({"category": "beauty"})',
            "function": cheapest_in_category_tool,
        },
        {
            "name": "list_by_category",
            "description": 'List category. Example: list_by_category({"category": "beauty"})',
            "function": list_by_category_tool,
        },
    ]


_TOOL_FUNCS: Dict[str, Callable[[str], str]] = {
    "refresh_products": lambda args: refresh_cache(),
    "search_products": search_products,
    "query_products_sql": query_products_sql,
    "list_by_category": list_by_category,
    "get_product_by_id": get_product_by_id,
    "cheapest_in_category": cheapest_in_category,
}

PRODUCT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "refresh_products",
        "description": "Load or refresh product data from DummyJSON into local SQLite.",
        "function": _TOOL_FUNCS["refresh_products"],
    },
    {
        "name": "search_products",
        "description": "Search products with natural language and heuristics; returns at most 5 Markdown image results.",
        "function": _TOOL_FUNCS["search_products"],
    },
    {
        "name": "query_products_sql",
        "description": "Run a read-only SELECT query against the local products SQLite table.",
        "function": _TOOL_FUNCS["query_products_sql"],
    },
    {
        "name": "list_by_category",
        "description": "List products in a category. Args: category string.",
        "function": _TOOL_FUNCS["list_by_category"],
    },
    {
        "name": "get_product_by_id",
        "description": "Fetch exact product by id. Args: product id.",
        "function": _TOOL_FUNCS["get_product_by_id"],
    },
    {
        "name": "cheapest_in_category",
        "description": (
            "Return the cheapest product in a category. "
            'Example: cheapest_in_category({"category": "beauty"})'
        ),
        "function": _TOOL_FUNCS["cheapest_in_category"],
    },
]


def execute_tool(tool_name: str, args: str) -> str:
    if tool_name not in _TOOL_FUNCS:
        return json.dumps({"error": "HALLUCINATED_TOOL", "message": f"Tool '{tool_name}' does not exist"})
    try:
        return _TOOL_FUNCS[tool_name](args)
    except Exception as exc:
        return json.dumps({"error": "INVALID_ARGS", "message": str(exc), "received": args})


def _parse_query_and_limit(args: str) -> tuple[str, int]:
    payload = _parse_args(args)
    if isinstance(payload, dict):
        return str(payload.get("query", "")), int(payload.get("limit", 5))
    return str(payload), 5


def _parse_args(args: str) -> Any:
    cleaned = args.strip()
    if not cleaned:
        return ""
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned.strip("\"'")
