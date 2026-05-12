from typing import Optional

carts: dict[str, dict] = {}

VALID_COUPONS = {
    "DISCOUNT10": 0.10,
    "PROMO20": 0.20,
}


def get_cart(user_id: str) -> dict:
    if user_id not in carts:
        carts[user_id] = {"user_id": user_id, "items": [], "coupon": None}
    return carts[user_id]


def set_cart_item(user_id: str, product: dict, quantity: int) -> dict:
    cart = get_cart(user_id)
    existing = next((i for i in cart["items"] if i["product"]["id"] == product["id"]), None)
    if existing:
        existing["quantity"] = quantity
    else:
        cart["items"].append({"product": product, "quantity": quantity})
    if quantity <= 0:
        cart["items"] = [i for i in cart["items"] if i["product"]["id"] != product["id"]]
    return cart


def clear_cart(user_id: str):
    carts.pop(user_id, None)


def get_cart_total(cart: dict) -> float:
    return sum(i["product"]["price"] * i["quantity"] for i in cart["items"])


def get_cart_total_items(cart: dict) -> int:
    return sum(i["quantity"] for i in cart["items"])


def apply_coupon(user_id: str, code: str) -> bool:
    if code.upper() in VALID_COUPONS:
        get_cart(user_id)["coupon"] = code.upper()
        return True
    return False


def get_discount(cart: dict) -> float:
    if not cart.get("coupon"):
        return 0.0
    rate = VALID_COUPONS.get(cart["coupon"], 0.0)
    return get_cart_total(cart) * rate


def get_final_total(cart: dict) -> float:
    return get_cart_total(cart) - get_discount(cart)
