import yaml
from pathlib import Path

_BASE = Path(__file__).parent.parent


def load_settings() -> dict:
    with open(_BASE / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


settings = load_settings()
