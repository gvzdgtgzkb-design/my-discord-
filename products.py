import os
import json
import uuid
from typing import Optional

PRODUCTS_FILE = "data/products.json"

def load_products() -> list:
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_products(products: list):
    os.makedirs("data", exist_ok=True)
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

products: list = load_products()

def get_all_products() -> list:
    return products

def find_product(product_id: str) -> Optional[dict]:
    return next((p for p in products if p["id"] == product_id), None)

def add_product(name: str, description: str, image_url: str, emoji: str = "",
                price_1d: float = 0, price_7d: float = 0, price_31d: float = 0) -> dict:
    product = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "description": description,
        "image_url": image_url,
        "emoji": emoji,
        "prices": {
            "1day": price_1d,
            "7day": price_7d,
            "31day": price_31d,
        }
    }
    products.append(product)
    save_products(products)
    return product

def update_product_prices(product_id: str, price_1d: float = None,
                          price_7d: float = None, price_31d: float = None) -> bool:
    p = find_product(product_id)
    if not p:
        return False
    if price_1d is not None:
        p["prices"]["1day"] = price_1d
    if price_7d is not None:
        p["prices"]["7day"] = price_7d
    if price_31d is not None:
        p["prices"]["31day"] = price_31d
    save_products(products)
    return True

def set_product_image(product_id: str, image_url: str) -> bool:
    p = find_product(product_id)
    if not p:
        return False
    p["image_url"] = image_url
    save_products(products)
    return True

def remove_product(product_id: str) -> bool:
    global products
    original = len(products)
    products = [p for p in products if p["id"] != product_id]
    save_products(products)
    return len(products) < original

def format_price(amount: float) -> str:
    return f"${amount:.2f}" if amount > 0 else "—"
