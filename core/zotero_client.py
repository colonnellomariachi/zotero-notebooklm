from __future__ import annotations
import time
from pathlib import Path
from loguru import logger
from pyzotero import zotero

import config
from models import ZoteroCollection, ZoteroItem, ZoteroAttachment


def _client() -> zotero.Zotero:
    return zotero.Zotero(
        config.ZOTERO_USER_ID,
        config.ZOTERO_LIBRARY_TYPE,
        config.ZOTERO_API_KEY,
    )


def get_collections() -> list[ZoteroCollection]:
    z = _client()
    raw = z.everything(z.collections())
    result = []
    for c in raw:
        data = c.get("data", {})
        meta = c.get("meta", {})
        result.append(
            ZoteroCollection(
                key=data["key"],
                name=data["name"],
                item_count=meta.get("numItems", 0),
            )
        )
    return sorted(result, key=lambda c: c.name)


def get_collection_items(collection_key: str) -> list[ZoteroItem]:
    """Fetch top-level items only (no attachments). Use get_collection_items_with_attachments for sync."""
    z = _client()
    raw = z.everything(z.collection_items_top(collection_key))
    items = []
    for r in raw:
        data = r.get("data", {})
        if data.get("itemType") == "attachment":
            continue
        creators = data.get("creators", [])
        authors = [
            f"{c.get('lastName', '')} {c.get('firstName', '')}".strip()
            for c in creators
            if c.get("creatorType") == "author"
        ]
        date = data.get("date", "")
        year = date[:4] if date else None
        items.append(
            ZoteroItem(
                key=data["key"],
                title=data.get("title", "(no title)"),
                authors=authors,
                year=year,
                abstract=data.get("abstractNote"),
                item_type=data.get("itemType", ""),
            )
        )
    return items


def get_collection_items_with_attachments(collection_key: str) -> list[ZoteroItem]:
    """
    Fetch all items AND their attachments in a single bulk API call.
    Replaces the N+1 pattern of get_collection_items() + get_item_attachments() per item.
    """
    z = _client()
    raw = z.everything(z.collection_items(collection_key))

    items_data: dict[str, dict] = {}
    attachments_by_parent: dict[str, list[dict]] = {}

    for r in raw:
        data = r.get("data", {})
        key = data.get("key", "")
        if data.get("itemType") == "attachment":
            parent = data.get("parentItem")
            if parent:
                attachments_by_parent.setdefault(parent, []).append(data)
        else:
            items_data[key] = data

    items = []
    for key, data in items_data.items():
        creators = data.get("creators", [])
        authors = [
            f"{c.get('lastName', '')} {c.get('firstName', '')}".strip()
            for c in creators
            if c.get("creatorType") == "author"
        ]
        date = data.get("date", "")
        year = date[:4] if date else None

        attachments = []
        for att in attachments_by_parent.get(key, []):
            link_mode = att.get("linkMode", "")
            if link_mode not in ("linked_file", "imported_file", "imported_url"):
                continue
            path = att.get("path", "") or att.get("filename", "")
            content_type = att.get("contentType", "")
            if not path:
                continue
            resolved = resolve_linked_file_path(path)
            attachments.append(ZoteroAttachment(
                key=att["key"],
                title=att.get("title", path),
                path=path,
                resolved_path=resolved,
                content_type=content_type,
            ))

        items.append(ZoteroItem(
            key=key,
            title=data.get("title", "(no title)"),
            authors=authors,
            year=year,
            abstract=data.get("abstractNote"),
            item_type=data.get("itemType", ""),
            attachments=attachments,
        ))
    return items


def get_collection_pdf_count(collection_key: str) -> tuple[int, int]:
    """
    Return (item_count, pdf_count) for a collection using a single bulk API call.
    Used by the GUI to show accurate counts without N+1 overhead.
    """
    z = _client()
    raw = z.everything(z.collection_items(collection_key))

    top_level_keys: set[str] = set()
    parents_with_pdf: set[str] = set()

    for r in raw:
        data = r.get("data", {})
        if data.get("itemType") == "attachment":
            content_type = data.get("contentType", "")
            path = data.get("path", "") or data.get("filename", "")
            if "pdf" in content_type.lower() or path.lower().endswith(".pdf"):
                parent = data.get("parentItem")
                if parent:
                    parents_with_pdf.add(parent)
        else:
            top_level_keys.add(data.get("key", ""))

    return len(top_level_keys), len(parents_with_pdf)


def get_item_attachments(item_key: str) -> list[ZoteroAttachment]:
    """Fetch attachments for a single item. Prefer get_collection_items_with_attachments for bulk use."""
    z = _client()
    raw = z.children(item_key)
    attachments = []
    for r in raw:
        data = r.get("data", {})
        if data.get("itemType") != "attachment":
            continue
        link_mode = data.get("linkMode", "")
        if link_mode not in ("linked_file", "imported_file", "imported_url"):
            continue
        path = data.get("path", "") or data.get("filename", "")
        content_type = data.get("contentType", "")
        if not path:
            continue
        resolved = resolve_linked_file_path(path)
        attachments.append(
            ZoteroAttachment(
                key=data["key"],
                title=data.get("title", path),
                path=path,
                resolved_path=resolved,
                content_type=content_type,
            )
        )
    return attachments


def resolve_linked_file_path(attachment_path: str) -> Path | None:
    """
    Handle both absolute paths and relative 'attachments:...' paths.
    Returns None if the file cannot be found locally.

    Fallback: if the primary candidate doesn't exist, search for the filename
    inside linked_files_root() — catches absolute paths stored in Zotero with
    a stale/wrong base directory.
    """
    if attachment_path.startswith("attachments:"):
        relative = attachment_path[len("attachments:"):]
        root = config.linked_files_root()
        candidate = root / relative
    else:
        candidate = Path(attachment_path)

    if candidate.exists():
        return candidate

    # Fallback: try to find the file by name under the configured root
    root = config.linked_files_root()
    filename = candidate.name
    if filename:
        fallback = root / filename
        if fallback.exists():
            logger.debug(f"Resolved via fallback: {fallback}")
            return fallback
        # Also try one level deep (some libraries use author/year subfolders)
        matches = list(root.rglob(filename))
        if matches:
            logger.debug(f"Resolved via recursive search: {matches[0]}")
            return matches[0]

    logger.warning(f"File not found locally: {candidate}")
    return None


def export_note_to_zotero(item_key: str, note_content: str, note_title: str) -> bool:
    z = _client()
    template = z.item_template("note")
    template["note"] = f"<h1>{note_title}</h1>\n{note_content}"
    template["parentItem"] = item_key
    try:
        z.create_items([template])
        return True
    except Exception as e:
        logger.error(f"Failed to export note to Zotero item {item_key}: {e}")
        return False
