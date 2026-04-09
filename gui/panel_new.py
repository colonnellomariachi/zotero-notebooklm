from __future__ import annotations
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from loguru import logger

from models import ZoteroCollection
from core import zotero_client, notebooklm_client, sync  # noqa: F401 (zotero_client used for pdf count)


class PanelNew(ttk.Frame):
    """Panel A — Load New Collection into a new NotebookLM notebook."""

    def __init__(self, parent, collections: list[ZoteroCollection]):
        super().__init__(parent, padding=16)
        self._collections = collections
        self._collection_map: dict[str, ZoteroCollection] = {c.key: c for c in collections}
        self._running = False
        self._build_ui()

    def _build_ui(self):
        # Collection selector
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))

        ttk.Label(top, text="Zotero Collection:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._coll_var = tk.StringVar()
        self._coll_combo = ttk.Combobox(
            top,
            textvariable=self._coll_var,
            values=self._combo_labels(),
            state="readonly",
            width=50,
        )
        self._coll_combo.grid(row=0, column=1, sticky="ew")
        self._coll_combo.bind("<<ComboboxSelected>>", self._on_collection_selected)

        # PDF count label (updated lazily when a collection is selected)
        self._pdf_count_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=self._pdf_count_var, foreground="gray").grid(
            row=0, column=2, sticky="w", padx=(8, 0)
        )

        # Notebook name
        ttk.Label(top, text="Notebook Name:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self._name_var = tk.StringVar()
        self._name_entry = ttk.Entry(top, textvariable=self._name_var, width=50)
        self._name_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0))

        # Options
        opts = ttk.Frame(self)
        opts.pack(fill="x", pady=(4, 8))
        self._metadata_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Include metadata note (titles, authors, abstracts)", variable=self._metadata_var).pack(side="left")

        # Action button
        self._btn = ttk.Button(self, text="Create Notebook", bootstyle="primary", command=self._start)
        self._btn.pack(anchor="w", pady=(0, 8))

        # Log area
        ttk.Label(self, text="Progress:").pack(anchor="w")
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True)
        self._log = tk.Text(log_frame, height=14, state="disabled", wrap="word", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        self._log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _combo_labels(self) -> list[str]:
        return [f"{c.name} ({c.item_count} items, {c.pdf_count} PDFs)" for c in self._collections]

    def _on_collection_selected(self, _event=None):
        idx = self._coll_combo.current()
        if idx < 0:
            return
        coll = self._collections[idx]
        if not self._name_var.get():
            self._name_var.set(coll.name)
        self._fetch_pdf_count(coll)

    def _fetch_pdf_count(self, coll):
        """Fetch item/PDF counts for the selected collection in a background thread."""
        self._pdf_count_var.set("counting PDFs...")

        def fetch():
            try:
                item_count, pdf_count = zotero_client.get_collection_pdf_count(coll.key)
                self.after(0, lambda: self._pdf_count_var.set(f"({item_count} items, {pdf_count} PDFs)"))
            except Exception:
                self.after(0, lambda: self._pdf_count_var.set(""))

        threading.Thread(target=fetch, daemon=True).start()

    def _log_msg(self, msg: str):
        """Thread-safe: can be called from any thread."""
        def _update():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _update)

    def _start(self):
        idx = self._coll_combo.current()
        if idx < 0:
            messagebox.showwarning("No selection", "Please select a Zotero collection.", parent=self)
            return
        notebook_name = self._name_var.get().strip()
        if not notebook_name:
            messagebox.showwarning("No name", "Please enter a notebook name.", parent=self)
            return

        coll = self._collections[idx]
        self._set_running(True)
        self._log_msg(f"Starting sync: '{coll.name}' → '{notebook_name}'")

        def run():
            try:
                self._log_msg("Creating NotebookLM notebook...")
                notebook_id = notebooklm_client.create_notebook(notebook_name)
                self._log_msg(f"Notebook created: {notebook_id}")

                import state as st
                st.upsert_notebook(
                    notebook_id,
                    collection_key=coll.key,
                    collection_name=coll.name,
                    synced_item_keys=[],
                )

                result = sync.sync_collection_to_notebook(
                    collection_key=coll.key,
                    notebook_id=notebook_id,
                    full_resync=True,
                    include_metadata_note=self._metadata_var.get(),
                    on_progress=self._log_msg,
                )
                self._log_msg("Done! " + result.summary())
            except Exception as e:
                self._log_msg(f"ERROR: {e}")
                logger.exception("Sync error in PanelNew")
            finally:
                self.after(0, lambda: self._set_running(False))

        threading.Thread(target=run, daemon=True).start()

    def _set_running(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        self._btn.configure(state=state)
        self._coll_combo.configure(state="disabled" if running else "readonly")

    def update_collections(self, collections: list[ZoteroCollection]):
        self._collections = collections
        self._coll_combo.configure(values=self._combo_labels())
