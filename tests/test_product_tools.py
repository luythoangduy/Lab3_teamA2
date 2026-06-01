import sqlite3

import pytest

from src.tools.product_tools import ProductCatalog


def seed_products(catalog: ProductCatalog) -> None:
    rows = [
        (
            1,
            "Pink Summer Dress",
            "A bright color garment for women with a young look.",
            "womens-dresses",
            39.99,
            12.0,
            4.8,
            20,
            "Demo",
            "SKU-1",
            "https://example.com/pink-dress.jpg",
            '["https://example.com/pink-dress.jpg"]',
            '["pink", "bright", "women"]',
        ),
        (
            2,
            "Black Office Chair",
            "Ergonomic furniture for work.",
            "furniture",
            89.99,
            5.0,
            4.6,
            15,
            "Demo",
            "SKU-2",
            "https://example.com/chair.jpg",
            '["https://example.com/chair.jpg"]',
            '["chair"]',
        ),
    ]
    with sqlite3.connect(catalog.db_path) as conn:
        conn.executemany(
            """
            INSERT INTO products (
                id, title, description, category, price, discount_percentage,
                rating, stock, brand, sku, thumbnail, images, tags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


def test_heuristic_search_returns_markdown_images(tmp_path):
    catalog = ProductCatalog(db_path=tmp_path / "products.sqlite3")
    seed_products(catalog)

    output = catalog.search_markdown("looks young garment for woman", limit=5)

    assert "Pink Summer Dress" in output
    assert "![Pink Summer Dress](https://example.com/pink-dress.jpg)" in output
    assert "Black Office Chair" not in output


def test_sql_tool_allows_select_only(tmp_path):
    catalog = ProductCatalog(db_path=tmp_path / "products.sqlite3")
    seed_products(catalog)

    products = catalog.query_sql("SELECT * FROM products WHERE category = 'womens-dresses'")

    assert len(products) == 1
    assert products[0]["title"] == "Pink Summer Dress"


def test_sql_tool_blocks_write_queries(tmp_path):
    catalog = ProductCatalog(db_path=tmp_path / "products.sqlite3")
    seed_products(catalog)

    with pytest.raises(ValueError, match="Only SELECT"):
        catalog.query_sql("DELETE FROM products")
