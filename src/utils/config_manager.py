import json

CONFIG_FILE = "config/config.json"

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(new_data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(new_data, f, indent=4)