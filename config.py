from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH)


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


ZOTERO_API_KEY: str = get("ZOTERO_API_KEY")
ZOTERO_USER_ID: str = get("ZOTERO_USER_ID")
ZOTERO_LIBRARY_TYPE: str = get("ZOTERO_LIBRARY_TYPE", "user")
DROPBOX_BASE_PATH: str = get("DROPBOX_BASE_PATH", "")
ZOTERO_LINKED_FILES_BASE: str = get("ZOTERO_LINKED_FILES_BASE", "")


def linked_files_root() -> Path:
    """Return the root folder where Zotero linked files live."""
    base = Path(DROPBOX_BASE_PATH)
    if ZOTERO_LINKED_FILES_BASE:
        base = base / ZOTERO_LINKED_FILES_BASE
    return base


def reload() -> None:
    """Re-read .env (called after user edits settings in the GUI)."""
    load_dotenv(_ENV_PATH, override=True)
    global ZOTERO_API_KEY, ZOTERO_USER_ID, ZOTERO_LIBRARY_TYPE
    global DROPBOX_BASE_PATH, ZOTERO_LINKED_FILES_BASE
    ZOTERO_API_KEY = get("ZOTERO_API_KEY")
    ZOTERO_USER_ID = get("ZOTERO_USER_ID")
    ZOTERO_LIBRARY_TYPE = get("ZOTERO_LIBRARY_TYPE", "user")
    DROPBOX_BASE_PATH = get("DROPBOX_BASE_PATH", "")
    ZOTERO_LINKED_FILES_BASE = get("ZOTERO_LINKED_FILES_BASE", "")
