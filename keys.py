import os
import json
from typing import Optional

KEYS_FILE = "data/keys.json"

def load_keys() -> dict:
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_keys(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

keys_db: dict = load_keys()

def add_key(product_id: str, key: str):
    if product_id not in keys_db:
        keys_db[product_id] = []
    if key not in keys_db[product_id]:
        keys_db[product_id].append(key)
        save_keys(keys_db)

def remove_key(product_id: str, key: str) -> bool:
    if product_id in keys_db and key in keys_db[product_id]:
        keys_db[product_id].remove(key)
        save_keys(keys_db)
        return True
    return False

def pop_key(product_id: str) -> Optional[str]:
    if keys_db.get(product_id):
        key = keys_db[product_id].pop(0)
        save_keys(keys_db)
        return key
    return None

def get_keys(product_id: str) -> list:
    return keys_db.get(product_id, [])

def count_keys(product_id: str) -> int:
    return len(keys_db.get(product_id, []))
