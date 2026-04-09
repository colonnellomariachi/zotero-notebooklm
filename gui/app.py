from __future__ import annotations
import threading
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from loguru import logger

from gui.panel_new import PanelNew
from gui.panel_update import PanelUpdate
from gui.settings_dialog import SettingsDialog
import config


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.title("Zotero ↔ NotebookLM Bridge")
        self.geometry("900x700")
        self.minsize(800, 600)

        self._panel_new: PanelNew | None = None
        self._panel_update: PanelUpdate | None = None

        self._build_menu()
        self._build_ui()
        self._load_data_async()

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        app_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="App", menu=app_menu)
        app_menu.add_command(label="Settings...", command=self._open_settings)
        app_menu.add_separator()
        app_menu.add_command(label="Quit", command=self.quit)

        view_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Light theme", command=lambda: self.style.theme_use("flatly"))
        view_menu.add_command(label="Dark theme", command=lambda: self.style.theme_use("darkly"))

    def _build_ui(self):
        # Header
        header = ttk.Frame(self, padding=(16, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Zotero ↔ NotebookLM Bridge", font=("", 14, "bold")).pack(side="left")
        ttk.Button(header, text="Settings", bootstyle="secondary-outline", command=self._open_settings).pack(side="right")

        ttk.Separator(self).pack(fill="x")

        # Notebook tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Placeholder frames while loading
        self._tab_new = ttk.Frame(self._notebook)
        self._tab_update = ttk.Frame(self._notebook)
        self._notebook.add(self._tab_new, text="Load New Collection")
        self._notebook.add(self._tab_update, text="Update Existing Notebooks")

        ttk.Label(self._tab_new, text="Loading Zotero collections...").pack(pady=40)
        ttk.Label(self._tab_update, text="Loading notebooks...").pack(pady=40)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self, textvariable=self._status_var, relief="sunken", anchor="w", padding=(8, 2))
        status_bar.pack(fill="x", side="bottom")

    def _load_data_async(self):
        self._status_var.set("Connecting to Zotero and NotebookLM...")

        def load():
            collections = []
            notebooks = []
            errors = []

            try:
                from core import zotero_client
                self.after(0, lambda: self._status_var.set("Fetching Zotero collections..."))
                collections = zotero_client.get_collections()
                # Enrich with PDF counts (may be slow for large libraries)
                # We skip per-item PDF counting here for speed; panels can refresh on demand
            except Exception as e:
                errors.append(f"Zotero error: {e}")
                logger.error(f"Failed to load Zotero collections: {e}")

            try:
                from core import notebooklm_client
                self.after(0, lambda: self._status_var.set("Fetching NotebookLM notebooks..."))
                notebooks = notebooklm_client.list_notebooks()
            except Exception as e:
                errors.append(f"NotebookLM error: {e}")
                logger.warning(f"Failed to load notebooks: {e}")

            self.after(0, lambda: self._on_data_loaded(collections, notebooks, errors))

        threading.Thread(target=load, daemon=True).start()

    def _on_data_loaded(self, collections, notebooks, errors):
        # Rebuild tab_new
        for w in self._tab_new.winfo_children():
            w.destroy()
        self._panel_new = PanelNew(self._tab_new, collections)
        self._panel_new.pack(fill="both", expand=True)

        # Rebuild tab_update
        for w in self._tab_update.winfo_children():
            w.destroy()
        self._panel_update = PanelUpdate(self._tab_update, notebooks)
        self._panel_update.pack(fill="both", expand=True)

        if errors:
            self._status_var.set("Loaded with errors — check Settings")
            messagebox.showwarning(
                "Startup warnings",
                "Some services could not be reached:\n\n" + "\n".join(errors),
                parent=self,
            )
        else:
            self._status_var.set(f"Ready — {len(collections)} collections, {len(notebooks)} notebooks loaded")

    def _open_settings(self):
        SettingsDialog(self)
