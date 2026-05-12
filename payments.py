import os
import json

PAYMENTS_FILE = "data/payments.json"

DEFAULT_PAYMENTS = {
    "binance": "",
    "upi_qr_url": "",
}

def load_payments() -> dict:
    if os.path.exists(PAYMENTS_FILE):
        with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_PAYMENTS.items():
                if k not in data:
                    data[k] = v
            return data
    return DEFAULT_PAYMENTS.copy()

def save_payments(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

payment_config: dict = load_payments()

def set_binance(binance_id: str):
    payment_config["binance"] = binance_id
    save_payments(payment_config)

def set_upi_qr_url(url: str):
    payment_config["upi_qr_url"] = url
    save_payments(payment_config)

def get_binance() -> str:
    return payment_config.get("binance", "")

def get_upi_qr_url() -> str:
    return payment_config.get("upi_qr_url", "")
