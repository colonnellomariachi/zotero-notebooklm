from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from pathlib import Path
import config

_ENV_PATH = Path(__file__).parent.parent / ".env"

_FIELDS = [
    ("ZOTERO_API_KEY", "Zotero API Key", False),
    ("ZOTERO_USER_ID", "Zotero User ID", False),
    ("ZOTERO_LIBRARY_TYPE", "Library Type (user / group)", False),
    ("DROPBOX_BASE_PATH", "Dropbox Base Path", False),
    ("ZOTERO_LINKED_FILES_BASE", "Zotero Linked Files Subfolder (optional)", False),
]


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings — Credentials")
        self.resizable(False, False)
        self.grab_set()

        current = self._read_env()
        self._vars: dict[str, tk.StringVar] = {}

        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)

        for i, (key, label, secret) in enumerate(_FIELDS):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            var = tk.StringVar(value=current.get(key, ""))
            self._vars[key] = var
            show = "*" if secret else ""
            ttk.Entry(frame, textvariable=var, width=50, show=show).grid(row=i, column=1, sticky="ew")

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(_FIELDS), column=0, columnspan=2, pady=(16, 0))
        ttk.Button(btn_frame, text="Save", bootstyle="success", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancel", bootstyle="secondary", command=self.destroy).pack(side="left", padx=4)

    def _read_env(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if not _ENV_PATH.exists():
            return result
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
        return result

    def _save(self):
        current = self._read_env()
        for key, var in self._vars.items():
            current[key] = var.get().strip()
        lines = [f"{k}={v}" for k, v in current.items()]
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        config.reload()
        messagebox.showinfo("Settings", "Credentials saved and reloaded.", parent=self)
        self.destroy()
