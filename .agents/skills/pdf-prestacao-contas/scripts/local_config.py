"""Read machine/user settings from ignored artifacts, never from source constants."""
import json
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'artifacts' / 'local-config.json'


def load_config(path=None):
    target = Path(path) if path is not None else DEFAULT_CONFIG
    if not target.exists():
        if path is not None:
            raise FileNotFoundError(target)
        return {}
    data = json.loads(target.read_text(encoding='utf8'))
    if not isinstance(data, dict):
        raise ValueError('Local configuration must be a JSON object.')
    return data


def condominium_id(settings, explicit=None):
    value = explicit if explicit is not None else settings.get('condominium', {}).get('id')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Supply --condominio-id or set condominium.id in artifacts/local-config.json.')
    return value
