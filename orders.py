import os
import json
import uuid
from typing import Optional

ORDERS_FILE = "data/orders.json"

def load_orders() -> dict:
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_orders(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

pending_orders: dict = load_orders()

def create_order(user_id: int, username: str, product: dict,
                 duration: str, price: float, payment_method: str) -> str:
    order_id = str(uuid.uuid4())[:8].upper()
    pending_orders[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "username": username,
        "product_id": product["id"],
        "product_name": product["name"],
        "duration": duration,
        "price": price,
        "payment_method": payment_method,
        "status": "pending",
    }
    save_orders(pending_orders)
    return order_id

def get_order(order_id: str) -> Optional[dict]:
    return pending_orders.get(order_id)

def approve_order(order_id: str) -> Optional[dict]:
    order = pending_orders.get(order_id)
    if order:
        order["status"] = "approved"
        save_orders(pending_orders)
    return order

def reject_order(order_id: str) -> Optional[dict]:
    order = pending_orders.get(order_id)
    if order:
        order["status"] = "rejected"
        save_orders(pending_orders)
    return order

def delete_order(order_id: str):
    pending_orders.pop(order_id, None)
    save_orders(pending_orders)
