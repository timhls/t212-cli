import yaml
from pathlib import Path
from pydantic import ValidationError
from t212_cli.tax.models import TaxConfig, TaxInstrument

CONFIG_DIR = Path.home() / ".t212"
CONFIG_FILE = CONFIG_DIR / "tax_config.yml"


def load_tax_config() -> TaxConfig:
    if not CONFIG_FILE.exists():
        return TaxConfig()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    try:
        return TaxConfig(**data)
    except ValidationError:
        # Fallback if corrupt
        return TaxConfig()


def save_tax_config(config: TaxConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            config.model_dump(mode="json"),
            f,
            allow_unicode=True,
            default_flow_style=False,
        )


def get_instrument_config(isin: str) -> TaxInstrument | None:
    config = load_tax_config()
    return config.instruments.get(isin)


def update_instrument_config(isin: str, instrument: TaxInstrument) -> None:
    config = load_tax_config()
    config.instruments[isin] = instrument
    save_tax_config(config)
