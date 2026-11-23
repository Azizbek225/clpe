"""Plaginlarni yuklash: CLPE_PLUGIN_MODULES='["my_pkg.validators", "my_pkg.provider"]'.
Plagin modul import vaqtida register_validator / register_provider chaqiradi."""
import importlib
import json
import logging
import os

log = logging.getLogger("clpe.plugins")


def load_plugins() -> list[str]:
    raw = os.environ.get("CLPE_PLUGIN_MODULES", "[]")
    try:
        mods = json.loads(raw)
    except json.JSONDecodeError:
        mods = [m.strip() for m in raw.split(",") if m.strip()]
    loaded = []
    for m in mods:
        try:
            importlib.import_module(m)
            loaded.append(m)
        except Exception:  # noqa: BLE001
            log.exception("Plaginni yuklab bo'lmadi: %s", m)
    return loaded
