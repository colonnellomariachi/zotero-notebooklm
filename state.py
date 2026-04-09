from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from loguru import logger

STATE_FILE = Path(__file__).parent / "state.json"

_DEFAULT: dict = {"notebooks": {}}


def load() -> dict:
    if not STATE_FILE.exists():
        return dict(_DEFAULT)
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"state.json unreadable ({e}), starting fresh")
        return dict(_DEFAULT)


def save(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)  # atomic rename


def get_notebook_entry(notebook_id: str) -> dict | None:
    return load()["notebooks"].get(notebook_id)


def upsert_notebook(
    notebook_id: str,
    *,
    collection_key: str,
    collection_name: str,
    synced_item_keys: list[str],
) -> None:
    state = load()
    state["notebooks"][notebook_id] = {
        "zotero_collection_key": collection_key,
        "zotero_collection_name": collection_name,
        "last_sync": datetime.utcnow().isoformat(),
        "synced_item_keys": synced_item_keys,
    }
    save(state)


def get_synced_keys(notebook_id: str) -> list[str]:
    entry = get_notebook_entry(notebook_id)
    return entry.get("synced_item_keys", []) if entry else []
