# Zotero ↔ NotebookLM Bridge

A Python desktop application that bridges Zotero and Google NotebookLM. It reads Zotero collections, loads PDFs into NotebookLM notebooks, and can export NotebookLM notes back to Zotero as item notes.

## Requirements

- Python 3.11+
- A locally-mounted Dropbox folder containing your Zotero linked files
- A Zotero account with API access
- A Google account with access to NotebookLM

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```
ZOTERO_API_KEY=your_key_here
ZOTERO_USER_ID=your_user_id_here
ZOTERO_LIBRARY_TYPE=user        # or "group"
DROPBOX_BASE_PATH=C:\Users\Marco\Dropbox
ZOTERO_LINKED_FILES_BASE=       # optional subfolder inside Dropbox for Zotero files
```

**Where to find your Zotero credentials:**
- `ZOTERO_USER_ID` and `ZOTERO_API_KEY`: go to [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
- `ZOTERO_LIBRARY_TYPE`: use `user` for personal libraries, `group` for group libraries

**`DROPBOX_BASE_PATH`** must point to the root of your locally-synced Dropbox folder. Zotero attachment paths are resolved relative to this folder.

**`ZOTERO_LINKED_FILES_BASE`** is an optional subfolder within Dropbox where Zotero stores its linked files (e.g. `Zotero` if your files are at `Dropbox\Zotero\...`). Leave blank if Zotero files are directly under `DROPBOX_BASE_PATH`.

## First Run — Google Authentication

On the first launch, `notebooklm-py` will open a browser window to authenticate with your Google account. Follow the prompts and grant access. The credentials are cached locally by the library and subsequent runs will not require re-authentication.

If authentication expires, the app will show a message asking you to re-authenticate.

## Running the App

```bash
python main.py
```

## Usage

### Panel A — Load New Collection

1. Select a Zotero collection from the dropdown (shows item and PDF counts)
2. Choose a name for the new NotebookLM notebook (defaults to collection name)
3. Optionally include a metadata context note (titles, authors, abstracts)
4. Click **Create Notebook** — progress is shown in the log area

### Panel B — Update Existing Notebooks

1. See all NotebookLM notebooks previously created by this app
2. Select one or more notebooks to update
3. Choose update mode:
   - **Add new items only** — uploads PDFs added to Zotero since the last sync
   - **Full re-sync** — reloads all sources from scratch
4. Click **Update Selected**

### Settings

Use **App > Settings** (or the Settings button) to edit `.env` values without leaving the app.

### Theme

Use **View > Light theme** or **View > Dark theme** to switch between `flatly` and `darkly`.

## Project Structure

```
zotero-notebooklm/
├── main.py                 # entry point
├── config.py               # loads .env
├── models.py               # Pydantic models
├── state.py                # state.json read/write
├── core/
│   ├── zotero_client.py    # Zotero API wrapper
│   ├── notebooklm_client.py# NotebookLM wrapper
│   └── sync.py             # sync logic
├── gui/
│   ├── app.py              # main window
│   ├── panel_new.py        # Panel A
│   ├── panel_update.py     # Panel B
│   └── settings_dialog.py  # Settings popup
├── state.json              # auto-generated, tracks sync state
├── .env                    # credentials (never commit)
└── .env.example            # template
```

## How PDF Resolution Works

All PDFs are expected to be **Zotero linked files** stored in a locally-mounted Dropbox folder — they are never uploaded to Zotero Cloud. When syncing, the app resolves attachment paths as follows:

- **Absolute path** (e.g. `C:\Users\Marco\Dropbox\Zotero\papers\file.pdf`) — used directly
- **Relative path** (e.g. `attachments:subfolder/file.pdf`) — resolved against `DROPBOX_BASE_PATH` + `ZOTERO_LINKED_FILES_BASE`

If a file is not found locally, it is logged as a warning and skipped — the sync continues with the remaining items.

## Testing the Zotero Connection

```bash
python -c "from core.zotero_client import get_collections; print(get_collections())"
```

## State File

`state.json` is auto-generated and tracks which Zotero items have been synced to each notebook. It is used to detect new items on incremental syncs. If the file becomes corrupted, it is discarded and a fresh sync is performed.

Do not commit `state.json` or `.env` to version control.
