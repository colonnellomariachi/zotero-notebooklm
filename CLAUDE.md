# Zotero ↔ NotebookLM Bridge

## Project Overview

A Python desktop application that bridges Zotero and Google NotebookLM. It reads Zotero collections, loads PDFs into NotebookLM notebooks, and exports NotebookLM notes/query results back to Zotero as item notes.

The app has a **graphical interface** (not CLI) as its primary entry point.

---

## Tech Stack

- **Python 3.11+**
- **GUI**: `tkinter` (stdlib, no extra install) with `ttkbootstrap` for modern styling
- **Zotero**: `pyzotero` library (Zotero REST API v3)
- **NotebookLM**: `notebooklm-py` (unofficial Python API, browser-automation based)
- **Config**: `python-dotenv` for credentials, `pydantic` for config models
- **Async**: `asyncio` + `threading` to keep GUI responsive during long operations
- **Logging**: `loguru` with a scrollable log panel in the GUI

---

## Credentials (`.env` file — never commit)

```
ZOTERO_API_KEY=your_key_here
ZOTERO_USER_ID=your_user_id_here
ZOTERO_LIBRARY_TYPE=user        # or "group"
DROPBOX_BASE_PATH=C:\Users\Marco\Dropbox   # or /home/marco/Dropbox on Linux/Mac
ZOTERO_LINKED_FILES_BASE=       # optional: subfolder inside Dropbox for Zotero files
```

Google auth for `notebooklm-py` is handled interactively on first run (browser popup), then cached by the library.

---

## PDF / File Access — IMPORTANT

All PDFs are stored as **Zotero linked files** on a locally-mounted Dropbox folder. They are NOT uploaded to Zotero Cloud.

When reading Zotero attachments:
1. Get the `path` field from the attachment metadata
2. Zotero may return paths in two formats — handle both:
   - **Absolute path**: e.g. `C:\Users\Marco\Dropbox\Zotero\papers\file.pdf`
   - **Relative path with prefix**: e.g. `attachments:subfolder/file.pdf` → resolve against `DROPBOX_BASE_PATH + ZOTERO_LINKED_FILES_BASE`
3. Check `os.path.exists()` before passing to NotebookLM
4. If a file is not found locally, log a warning and skip — do not crash

No temporary downloads are needed. Pass the resolved local path directly to `notebooklm-py`.

---

## GUI Structure

The app has a **single main window** with two clearly separated panels:

### Panel A — "Load New Collection"

Allows the user to:
- Browse and select a Zotero collection from a dropdown (populated on startup via API)
- See a preview of how many items / PDFs are in that collection
- Choose a name for the new NotebookLM notebook (default: collection name)
- Optionally include item metadata (title, author, year, abstract) as a pinned context note in the notebook
- Click **"Create Notebook"** to start the process
- See a real-time progress log (scrollable text area)

### Panel B — "Update Existing Notebooks"

Allows the user to:
- See a list of existing NotebookLM notebooks (fetched via notebooklm-py)
- For each notebook, show the associated Zotero collection (stored in a local `state.json` mapping)
- Select one or more notebooks to update
- Choose update mode:
  - **Add new items only** (items added to the Zotero collection since last sync)
  - **Full re-sync** (reload all sources from scratch)
- Click **"Update Selected"** to start
- See a real-time progress log

### Shared elements
- Status bar at the bottom showing last sync time per notebook
- A "Settings" button to edit `.env` values without leaving the app
- All long-running operations run in background threads — GUI must never freeze

---

## State Management

Maintain a local `state.json` file (same folder as the script) that maps:

```json
{
  "notebooks": {
    "notebooklm_notebook_id": {
      "zotero_collection_key": "ABC123",
      "zotero_collection_name": "Brazil Networks",
      "last_sync": "2026-04-01T14:32:00",
      "synced_item_keys": ["ZOT001", "ZOT002"]
    }
  }
}
```

Use this to:
- Know which Zotero collection corresponds to which notebook
- Detect new items since last sync (diff against `synced_item_keys`)
- Display sync status in the GUI

---

## Core Functions

```python
# zotero_client.py
get_collections() -> list[ZoteroCollection]
get_collection_items(collection_key: str) -> list[ZoteroItem]          # top-level only, no attachments
get_collection_items_with_attachments(collection_key: str) -> list[ZoteroItem]  # bulk: 1 API call, items + attachments
get_collection_pdf_count(collection_key: str) -> tuple[int, int]       # (item_count, pdf_count), 1 API call
get_item_attachments(item_key: str) -> list[ZoteroAttachment]          # single-item fallback
resolve_linked_file_path(attachment_path: str) -> Path | None
export_note_to_zotero(item_key: str, note_content: str, note_title: str) -> bool

# notebooklm_client.py
list_notebooks() -> list[NotebookInfo]
create_notebook(title: str) -> str                                      # returns notebook_id
add_sources_to_notebook(notebook_id: str, sources: list[Path | str]) -> bool
add_context_note(notebook_id: str, markdown_text: str) -> bool
upload_and_annotate(notebook_id, sources, context_note=None, on_progress=None) -> bool  # single session
query_notebook(notebook_id: str, prompt: str) -> str
export_notebook_notes(notebook_id: str) -> list[str]

# sync.py
sync_collection_to_notebook(collection_key, notebook_id, full_resync=False) -> SyncResult
build_metadata_note(items: list[ZoteroItem]) -> str
```

---

## Error Handling

- Zotero API rate limits: respect 429 responses with exponential backoff
- Missing PDFs: log warning, skip item, continue sync — never abort the whole operation
- NotebookLM browser auth expired: catch the exception, surface a clear message in the GUI asking the user to re-authenticate
- `state.json` corruption: if unparseable, start fresh with a warning — do not crash

---

## Project Structure

```
zotero-notebooklm/
├── CLAUDE.md               ← this file
├── main.py                 ← entry point, launches GUI
├── gui/
│   ├── app.py              ← main window
│   ├── panel_new.py        ← Panel A: Load New Collection
│   ├── panel_update.py     ← Panel B: Update Existing
│   └── settings_dialog.py  ← Settings popup
├── core/
│   ├── zotero_client.py
│   ├── notebooklm_client.py
│   └── sync.py
├── models.py               ← Pydantic models for ZoteroItem, NotebookInfo, SyncResult etc.
├── state.py                ← state.json read/write
├── config.py               ← loads .env via dotenv
├── state.json              ← auto-generated, gitignored
├── .env                    ← credentials, gitignored
├── requirements.txt
└── README.md
```

---

## Style & UX Notes

- Use `ttkbootstrap` theme `flatly` (light) or `darkly` (dark) — add a toggle
- Progress logs should auto-scroll to bottom as new lines arrive
- Buttons should be disabled (greyed out) while an operation is running
- Show item counts in the collection dropdown: "Brazil Networks (47 items, 31 PDFs)"
- When sync completes, show a summary: "✓ 31 sources uploaded, 3 files not found, 2 skipped (no PDF)"

---

## Performance & Correctness Notes

- **Bulk fetch pattern**: always use `get_collection_items_with_attachments()` in sync — it fetches all items + attachments in one API call instead of N+1. `get_item_attachments()` is kept only as a single-item fallback.
- **PDF count**: use `get_collection_pdf_count()` from the GUI (one bulk call per collection, triggered lazily on selection — not at startup).
- **NotebookLM sessions**: use `upload_and_annotate()` when you need to upload sources + add a context note — it opens a single browser session for both operations.
- **Thread safety**: all tkinter widget updates from background threads must go through `self.after(0, fn)`. Both `_log_msg()` in `panel_new.py` and `panel_update.py` already do this.
- **State writes**: `state.py` writes to a `.tmp` file then renames atomically — do not bypass this.
- **State reads**: call `state.get_notebook_entry()` once per operation and reuse the result — avoid redundant disk reads.

## Development Notes

- Always run `python main.py` to test — not individual modules
- Test Zotero connection: `python -c "from core.zotero_client import get_collections; print(get_collections())"`
- NotebookLM first run requires interactive browser login — document this clearly in README
- Do not hardcode any paths, credentials, or user IDs — always use config.py / .env
