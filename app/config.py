import json
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

_BASE = Path(__file__).parent.parent

load_dotenv(_BASE / ".env")


def load_settings() -> dict:
    with open(_BASE / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


settings = load_settings()

# ЮКасса
yookassa_shop_id: str = os.getenv("YOOKASSA_SHOP_ID", "")
yookassa_secret_key: str = os.getenv("YOOKASSA_SECRET_KEY", "")
site_url: str = os.getenv("SITE_URL", "http://localhost:8000")

# SMTP
smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
smtp_user: str = os.getenv("SMTP_USER", "")
smtp_password: str = os.getenv("SMTP_PASSWORD", "")
admin_email: str = os.getenv("ADMIN_EMAIL", "")

# stampim.space (heat_monitor)
heat_monitor_url: str = os.getenv("HEAT_MONITOR_URL", "")
heat_monitor_api_key: str = os.getenv("HEAT_MONITOR_API_KEY", "")

# Узлы мониторинга
nodes_config_path: str = os.getenv("NODES_CONFIG_PATH", "")


def _load_nodes() -> list:
    if not nodes_config_path:
        return []
    try:
        with open(nodes_config_path, encoding="utf-8") as f:
            data = json.load(f)
        return [{"id": k, "address": v["address"]} for k, v in data.items()]
    except Exception:
        return []


nodes: list = _load_nodes()
