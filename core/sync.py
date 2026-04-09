from __future__ import annotations
from pathlib import Path
from loguru import logger

import state
from models import ZoteroItem, SyncResult
from core import zotero_client, notebooklm_client


def build_metadata_note(items: list[ZoteroItem]) -> str:
    """Build a markdown summary of the collection to pin as context."""
    lines = ["# Collection Metadata\n"]
    for item in items:
        authors = ", ".join(item.authors) if item.authors else "Unknown"
        year = item.year or "n.d."
        lines.append(f"## {item.title}")
        lines.append(f"**Authors:** {authors}  |  **Year:** {year}")
        if item.abstract:
            lines.append(f"\n{item.abstract}\n")
        lines.append("")
    return "\n".join(lines)


def sync_collection_to_notebook(
    collection_key: str,
    notebook_id: str,
    full_resync: bool = False,
    include_metadata_note: bool = True,
    on_progress=None,  # callable(str) for GUI log
) -> SyncResult:
    """
    Sync a Zotero collection's PDFs to a NotebookLM notebook.

    Args:
        collection_key: Zotero collection key
        notebook_id: NotebookLM notebook ID
        full_resync: if True, treat all items as new (re-upload everything)
        include_metadata_note: if True, add a pinned metadata note
        on_progress: optional callback for progress messages
    """
    def log(msg: str):
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    result = SyncResult(notebook_id=notebook_id, collection_key=collection_key)

    # Load state once — used both for already_synced check and for collection_name at save time
    entry = state.get_notebook_entry(notebook_id) or {}
    already_synced = set(entry.get("synced_item_keys", [])) if not full_resync else set()

    log("Fetching collection items and attachments from Zotero...")
    items = zotero_client.get_collection_items_with_attachments(collection_key)
    log(f"Found {len(items)} items in collection.")

    new_items = [i for i in items if i.key not in already_synced]
    log(f"{len(new_items)} items to process.")

    sources_to_add: list[Path] = []
    synced_keys = list(already_synced)

    for item in new_items:
        pdf_attachments = [
            a for a in item.attachments
            if "pdf" in a.content_type.lower() or a.path.lower().endswith(".pdf")
        ]

        if not pdf_attachments:
            log(f"  Skipping '{item.title}' — no PDF attachment")
            result.items_skipped_no_pdf += 1
            continue

        found_pdf = False
        for att in pdf_attachments:
            if att.resolved_path and att.resolved_path.exists():
                sources_to_add.append(att.resolved_path)
                found_pdf = True
                log(f"  Queued: {att.resolved_path.name}")
                break
            else:
                log(f"  File not found: {att.path}")
                result.files_not_found += 1

        if found_pdf:
            synced_keys.append(item.key)

    if sources_to_add:
        log(f"Uploading {len(sources_to_add)} PDF(s) to NotebookLM...")
        context_note = build_metadata_note(items) if include_metadata_note and (full_resync or not already_synced) else None
        if context_note:
            log("Will also add metadata context note.")
        ok = notebooklm_client.upload_and_annotate(
            notebook_id,
            sources_to_add,
            context_note=context_note,
            on_progress=on_progress,
        )
        if ok:
            result.sources_uploaded = len(sources_to_add)
            log("Upload complete.")
        else:
            result.success = False
            result.errors.append("Failed to upload some sources to NotebookLM")
            log("ERROR: Upload to NotebookLM failed.")
    elif include_metadata_note and (full_resync or not already_synced):
        # No sources but still need to add the metadata note
        log("Adding metadata context note (no new PDFs)...")
        notebooklm_client.add_context_note(notebook_id, build_metadata_note(items))

    # Persist updated state
    state.upsert_notebook(
        notebook_id,
        collection_key=collection_key,
        collection_name=entry.get("zotero_collection_name", collection_key),
        synced_item_keys=synced_keys,
    )

    log(result.summary())
    return result
