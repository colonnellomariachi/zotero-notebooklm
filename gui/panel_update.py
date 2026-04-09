from __future__ import annotations
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from loguru import logger

import state as st
from models import NotebookInfo
from core import sync


class PanelUpdate(ttk.Frame):
    """Panel B — Update existing NotebookLM notebooks."""

    def __init__(self, parent, notebooks: list[NotebookInfo]):
        super().__init__(parent, padding=16)
        self._notebooks = notebooks
        self._running = False
        self._build_ui()
        self._populate_table()

    def _build_ui(self):
        ttk.Label(self, text="Existing Notebooks:").pack(anchor="w")

        # Notebook list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, pady=(4, 8))

        cols = ("title", "collection", "last_sync", "items")
        self._tree = ttk.Treeview(
            list_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            height=8,
        )
        self._tree.heading("title", text="Notebook")
        self._tree.heading("collection", text="Zotero Collection")
        self._tree.heading("last_sync", text="Last Sync")
        self._tree.heading("items", text="Items Synced")
        self._tree.column("title", width=220)
        self._tree.column("collection", width=200)
        self._tree.column("last_sync", width=140)
        self._tree.column("items", width=90, anchor="center")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Options
        opts = ttk.Frame(self)
        opts.pack(fill="x", pady=(0, 8))
        ttk.Label(opts, text="Update mode:").pack(side="left", padx=(0, 8))
        self._mode_var = tk.StringVar(value="new")
        ttk.Radiobutton(opts, text="Add new items only", variable=self._mode_var, value="new").pack(side="left", padx=4)
        ttk.Radiobutton(opts, text="Full re-sync", variable=self._mode_var, value="full").pack(side="left", padx=4)

        # Button
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", pady=(0, 8))
        self._btn = ttk.Button(btn_frame, text="Update Selected", bootstyle="warning", command=self._start)
        self._btn.pack(side="left")
        ttk.Button(btn_frame, text="Refresh List", bootstyle="secondary-outline", command=self._refresh).pack(side="left", padx=8)

        # Log
        ttk.Label(self, text="Progress:").pack(anchor="w")
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True)
        self._log = tk.Text(log_frame, height=10, state="disabled", wrap="word", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        self._log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _populate_table(self):
        self._tree.delete(*self._tree.get_children())
        state_data = st.load()
        for nb in self._notebooks:
            entry = state_data["notebooks"].get(nb.notebook_id, {})
            coll_name = entry.get("zotero_collection_name", "—")
            last_sync = entry.get("last_sync", "never")
            if last_sync != "never":
                last_sync = last_sync[:16].replace("T", " ")
            n_items = len(entry.get("synced_item_keys", []))
            self._tree.insert("", "end", iid=nb.notebook_id, values=(nb.title, coll_name, last_sync, n_items))

    def _log_msg(self, msg: str):
        """Thread-safe: can be called from any thread."""
        def _update():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _update)

    def _start(self):
        selected = self._tree.selection()
        if not selected:
            messagebox.showwarning("No selection", "Select at least one notebook.", parent=self)
            return
        full_resync = self._mode_var.get() == "full"
        self._set_running(True)

        def run():
            for notebook_id in selected:
                entry = st.get_notebook_entry(notebook_id)
                if not entry:
                    self._log_msg(f"No state entry for notebook {notebook_id}, skipping.")
                    continue
                collection_key = entry["zotero_collection_key"]
                self._log_msg(f"\nUpdating notebook {notebook_id}...")
                try:
                    result = sync.sync_collection_to_notebook(
                        collection_key=collection_key,
                        notebook_id=notebook_id,
                        full_resync=full_resync,
                        on_progress=self._log_msg,
                    )
                    self._log_msg("Done! " + result.summary())
                except Exception as e:
                    self._log_msg(f"ERROR: {e}")
                    logger.exception(f"Sync error for notebook {notebook_id}")
            self.after(0, lambda: (self._set_running(False), self._populate_table()))

        threading.Thread(target=run, daemon=True).start()

    def _refresh(self):
        from core import notebooklm_client
        try:
            self._notebooks = notebooklm_client.list_notebooks()
            self._populate_table()
        except Exception as e:
            messagebox.showerror("Error", f"Could not fetch notebooks:\n{e}", parent=self)

    def _set_running(self, running: bool):
        self._running = running
        self._btn.configure(state="disabled" if running else "normal")
