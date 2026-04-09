from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import browser_cookie3
    _BC3_AVAILABLE = True
except ImportError:
    _BC3_AVAILABLE = False

# Domains to harvest when reading from the browser
_GOOGLE_DOMAINS = ("google.com", "notebooklm.google.com")

# browser-cookie3 loader functions by name
_BROWSER_LOADERS: dict[str, Any] = {}
if _BC3_AVAILABLE:
    for _name in ("chrome", "chromium", "edge", "brave", "opera", "opera_gx",
                  "vivaldi", "arc", "firefox", "librewolf"):
        if hasattr(browser_cookie3, _name):
            _BROWSER_LOADERS[_name] = getattr(browser_cookie3, _name)

try:
    from notebooklm.paths import get_storage_path
    from notebooklm.auth import MINIMUM_REQUIRED_COOKIES, ALLOWED_COOKIE_DOMAINS
    _NLM_AVAILABLE = True
except ImportError:
    _NLM_AVAILABLE = False
    def get_storage_path() -> Path:  # type: ignore[misc]
        return Path.home() / ".notebooklm" / "storage_state.json"
    MINIMUM_REQUIRED_COOKIES = {"SID"}
    ALLOWED_COOKIE_DOMAINS = {".google.com", "notebooklm.google.com", ".googleusercontent.com"}

# Cookie-Editor sameSite values → Playwright sameSite values
_SAMESITE_MAP = {
    "unspecified": "None",
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
}


def get_auth_status() -> dict:
    """
    Return current authentication status.
    Result keys: exists (bool), valid (bool), cookie_count (int), missing (set[str])
    """
    path = get_storage_path()
    if not path.exists():
        return {"exists": False, "valid": False, "cookie_count": 0, "missing": MINIMUM_REQUIRED_COOKIES}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        names = {c.get("name") for c in data.get("cookies", [])}
        missing = MINIMUM_REQUIRED_COOKIES - names
        return {
            "exists": True,
            "valid": len(missing) == 0,
            "cookie_count": len(names),
            "missing": missing,
        }
    except Exception as e:
        logger.warning(f"Could not read storage_state.json: {e}")
        return {"exists": True, "valid": False, "cookie_count": 0, "missing": MINIMUM_REQUIRED_COOKIES}


def _convert_cookie_editor(cookies_list: list[dict]) -> dict:
    """
    Convert Cookie-Editor JSON array format to Playwright storage_state format.

    Cookie-Editor exports cookies as a flat list; Playwright wraps them in
    {"cookies": [...], "origins": []}.  Field names and sameSite values differ.
    """
    converted = []
    for c in cookies_list:
        name = c.get("name", "")
        value = c.get("value", "")
        if not name:
            continue

        expiration = c.get("expirationDate", c.get("expires", -1))
        if isinstance(expiration, float):
            expiration = int(expiration)

        same_site_raw = c.get("sameSite", "unspecified").lower()
        same_site = _SAMESITE_MAP.get(same_site_raw, "None")

        converted.append({
            "name": name,
            "value": value,
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "expires": expiration,
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": same_site,
        })

    return {"cookies": converted, "origins": []}


def _parse_input(json_str: str) -> dict[str, Any]:
    """
    Accept either:
    - Playwright storage_state format: {"cookies": [...], "origins": [...]}
    - Cookie-Editor format: [{...}, {...}]

    Returns a Playwright storage_state dict.
    Raises ValueError on unrecognised format.
    """
    data = json.loads(json_str)

    if isinstance(data, list):
        # Cookie-Editor format
        return _convert_cookie_editor(data)

    if isinstance(data, dict):
        if "cookies" in data:
            # Already Playwright format — normalise field names just in case
            return data
        raise ValueError(
            "Unrecognised dict format: expected a 'cookies' key (Playwright storage state) "
            "or a JSON array (Cookie-Editor export)."
        )

    raise ValueError("Expected a JSON object or array.")


def _validate(storage_state: dict) -> set[str]:
    """Return set of missing required cookie names (empty = OK)."""
    names = {c.get("name") for c in storage_state.get("cookies", [])}
    return MINIMUM_REQUIRED_COOKIES - names


def import_cookies(json_str: str) -> tuple[bool, str]:
    """
    Parse, validate, and save cookies to storage_state.json.

    Returns (success: bool, message: str).
    """
    try:
        storage_state = _parse_input(json_str.strip())
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except ValueError as e:
        return False, str(e)

    missing = _validate(storage_state)
    if missing:
        return False, (
            f"Missing required cookies: {', '.join(sorted(missing))}.\n"
            "Make sure you are logged into NotebookLM in your browser and export "
            "ALL cookies from the google.com domain."
        )

    path = get_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(storage_state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

    n = len(storage_state.get("cookies", []))
    logger.info(f"Google auth: saved {n} cookies to {path}")
    return True, f"Saved {n} cookies to {path}"


def import_cookies_from_file(file_path: str | Path) -> tuple[bool, str]:
    """Load cookies from a .json file and import them."""
    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Cannot read file: {e}"
    return import_cookies(text)


# ── Browser-direct import (browser-cookie3) ───────────────────────────────────

def available_browsers() -> list[str]:
    """Return list of browser names that browser-cookie3 can read."""
    return list(_BROWSER_LOADERS.keys())


def import_from_browser(browser_name: str) -> tuple[bool, str]:
    """
    Read Google cookies directly from an installed browser and save them.

    The browser must be CLOSED before calling this on Chrome/Edge/Brave
    (they lock the SQLite cookie database while running).
    Firefox can be read while open.

    Returns (success, message).
    """
    if not _BC3_AVAILABLE:
        return False, "browser-cookie3 is not installed."

    loader = _BROWSER_LOADERS.get(browser_name.lower())
    if loader is None:
        return False, f"Unknown browser: '{browser_name}'. Available: {list(_BROWSER_LOADERS)}"

    try:
        cookie_jar = loader(domain_name="google.com")
    except Exception as e:
        msg = str(e)
        if "database is locked" in msg.lower() or "unable to open" in msg.lower():
            return False, (
                f"Cannot read {browser_name} cookies — the browser is open.\n"
                f"Close {browser_name.capitalize()} completely and try again."
            )
        return False, f"Error reading {browser_name} cookies: {e}"

    now = time.time()
    cookies = []
    for c in cookie_jar:
        domain = c.domain if c.domain.startswith(".") else f".{c.domain}"
        # Keep only Google-related cookies
        if "google" not in domain:
            continue
        cookies.append({
            "name": c.name,
            "value": c.value,
            "domain": domain,
            "path": c.path or "/",
            "expires": int(c.expires) if c.expires else -1,
            "httpOnly": bool(getattr(c, "_rest", {}).get("HttpOnly")),
            "secure": bool(c.secure),
            "sameSite": "None",
        })

    if not cookies:
        return False, (
            f"No Google cookies found in {browser_name}.\n"
            "Make sure you are logged into notebooklm.google.com in that browser."
        )

    storage_state = {"cookies": cookies, "origins": []}
    missing = _validate(storage_state)
    if missing:
        return False, (
            f"Found {len(cookies)} Google cookies in {browser_name}, "
            f"but missing required: {', '.join(sorted(missing))}.\n"
            "Make sure you are logged into notebooklm.google.com in that browser."
        )

    path = get_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(storage_state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

    logger.info(f"Google auth: imported {len(cookies)} cookies from {browser_name}")
    return True, f"Imported {len(cookies)} cookies from {browser_name.capitalize()}."
