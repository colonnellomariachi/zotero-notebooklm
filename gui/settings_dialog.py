from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
import ttkbootstrap as ttk
from pathlib import Path
import config
from core.google_auth import (
    get_auth_status, import_cookies, import_cookies_from_file,
    import_from_browser, available_browsers,
)

_ENV_PATH = Path(__file__).parent.parent / ".env"

_FIELDS = [
    ("ZOTERO_API_KEY", "Zotero API Key", False),
    ("ZOTERO_USER_ID", "Zotero User ID", False),
    ("ZOTERO_LIBRARY_TYPE", "Library Type (user / group)", False),
    ("DROPBOX_BASE_PATH", "Dropbox Base Path", False),
    ("ZOTERO_LINKED_FILES_BASE", "Zotero Linked Files Subfolder (optional)", False),
]

_INSTRUCTIONS_BROWSER = (
    "Easiest method — no extensions needed:\n\n"
    "1. Log into https://notebooklm.google.com in Chrome, Edge, Firefox, or Brave\n\n"
    "2. Close the browser completely (required for Chrome/Edge/Brave;\n"
    "   Firefox can stay open)\n\n"
    "3. Click the 'Import from browser' button above and select your browser\n\n"
    "Your session is saved in ~/.notebooklm/storage_state.json (~1 year validity)."
)

_INSTRUCTIONS_MANUAL = (
    "Manual method (Cookie-Editor extension):\n\n"
    "1. Install 'Cookie-Editor' from your browser's extension store\n\n"
    "2. Go to https://notebooklm.google.com and log in\n\n"
    "3. Click Cookie-Editor → Export → Export as JSON\n\n"
    "4. Paste the JSON below or use 'Import from file...'"
)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(True, False)
        self.grab_set()
        self.minsize(560, 400)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Tab 1: Zotero credentials ──────────────────────────────────────────
        cred_frame = ttk.Frame(notebook, padding=16)
        notebook.add(cred_frame, text="Zotero Credentials")
        self._build_credentials_tab(cred_frame)

        # ── Tab 2: Google Auth ─────────────────────────────────────────────────
        auth_frame = ttk.Frame(notebook, padding=16)
        notebook.add(auth_frame, text="Google Auth")
        self._build_auth_tab(auth_frame)

    # ── Credentials tab ────────────────────────────────────────────────────────

    def _build_credentials_tab(self, frame: ttk.Frame):
        current = self._read_env()
        self._vars: dict[str, tk.StringVar] = {}

        for i, (key, label, secret) in enumerate(_FIELDS):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            var = tk.StringVar(value=current.get(key, ""))
            self._vars[key] = var
            show = "*" if secret else ""
            ttk.Entry(frame, textvariable=var, width=50, show=show).grid(row=i, column=1, sticky="ew")

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(_FIELDS), column=0, columnspan=2, pady=(16, 0))
        ttk.Button(btn_frame, text="Save", bootstyle="success", command=self._save_credentials).pack(side="left", padx=4)
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

    def _save_credentials(self):
        current = self._read_env()
        for key, var in self._vars.items():
            current[key] = var.get().strip()
        lines = [f"{k}={v}" for k, v in current.items()]
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        config.reload()
        messagebox.showinfo("Settings", "Credentials saved and reloaded.", parent=self)
        self.destroy()

    # ── Google Auth tab ────────────────────────────────────────────────────────

    def _build_auth_tab(self, frame: ttk.Frame):
        # Status row
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(status_frame, text="Status:").pack(side="left", padx=(0, 8))
        self._auth_status_var = tk.StringVar()
        self._auth_status_label = ttk.Label(status_frame, textvariable=self._auth_status_var, font=("", 9, "bold"))
        self._auth_status_label.pack(side="left")
        ttk.Button(status_frame, text="Refresh", bootstyle="secondary-outline",
                   command=self._refresh_auth_status).pack(side="right")
        self._refresh_auth_status()

        ttk.Separator(frame).pack(fill="x", pady=(0, 10))

        # ── Section 1: Import from browser ────────────────────────────────────
        ttk.Label(frame, text="Option 1 — Import directly from browser",
                  font=("", 9, "bold")).pack(anchor="w")

        instr1 = tk.Text(frame, height=5, wrap="word", font=("", 9),
                         relief="flat", background=frame.winfo_toplevel().cget("background"))
        instr1.insert("1.0", _INSTRUCTIONS_BROWSER)
        instr1.configure(state="disabled")
        instr1.pack(fill="x", pady=(4, 6))

        browsers = available_browsers()
        browser_btn_frame = ttk.Frame(frame)
        browser_btn_frame.pack(fill="x", pady=(0, 10))

        if browsers:
            for name in browsers:
                label = name.capitalize().replace("_gx", " GX").replace("_", " ")
                ttk.Button(
                    browser_btn_frame,
                    text=label,
                    bootstyle="primary-outline",
                    command=lambda b=name: self._import_from_browser(b),
                    width=10,
                ).pack(side="left", padx=(0, 6))
        else:
            ttk.Label(browser_btn_frame, text="browser-cookie3 not installed — run: pip install browser-cookie3",
                      foreground="gray").pack(side="left")

        ttk.Separator(frame).pack(fill="x", pady=(0, 10))

        # ── Section 2: Paste / file import ────────────────────────────────────
        ttk.Label(frame, text="Option 2 — Paste JSON (Cookie-Editor extension)",
                  font=("", 9, "bold")).pack(anchor="w")

        instr2 = tk.Text(frame, height=4, wrap="word", font=("", 9),
                         relief="flat", background=frame.winfo_toplevel().cget("background"))
        instr2.insert("1.0", _INSTRUCTIONS_MANUAL)
        instr2.configure(state="disabled")
        instr2.pack(fill="x", pady=(4, 6))

        self._paste_text = scrolledtext.ScrolledText(frame, height=5, font=("Consolas", 8), wrap="none")
        self._paste_text.pack(fill="both", expand=True, pady=(0, 8))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Import from file...", bootstyle="secondary-outline",
                   command=self._import_from_file).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Save pasted cookies", bootstyle="success",
                   command=self._save_cookies).pack(side="left")

    def _refresh_auth_status(self):
        status = get_auth_status()
        if status["valid"]:
            self._auth_status_var.set(f"Authenticated  ({status['cookie_count']} cookies)")
            self._auth_status_label.configure(bootstyle="success")
        elif status["exists"]:
            missing = ", ".join(sorted(status["missing"]))
            self._auth_status_var.set(f"Invalid — missing: {missing}")
            self._auth_status_label.configure(bootstyle="danger")
        else:
            self._auth_status_var.set("Not authenticated — no storage_state.json found")
            self._auth_status_label.configure(bootstyle="warning")

    def _save_cookies(self):
        json_str = self._paste_text.get("1.0", "end").strip()
        if not json_str:
            messagebox.showwarning("Empty", "Paste your cookies JSON first.", parent=self)
            return
        ok, msg = import_cookies(json_str)
        if ok:
            messagebox.showinfo("Google Auth", f"Cookies saved successfully.\n{msg}", parent=self)
            self._paste_text.delete("1.0", "end")
            self._refresh_auth_status()
        else:
            messagebox.showerror("Import failed", msg, parent=self)

    def _import_from_browser(self, browser_name: str):
        ok, msg = import_from_browser(browser_name)
        if ok:
            messagebox.showinfo("Google Auth",
                                f"Cookies imported successfully.\n{msg}", parent=self)
            self._refresh_auth_status()
        else:
            messagebox.showerror("Import failed", msg, parent=self)

    def _import_from_file(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select cookies JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        ok, msg = import_cookies_from_file(path)
        if ok:
            messagebox.showinfo("Google Auth", f"Cookies imported successfully.\n{msg}", parent=self)
            self._refresh_auth_status()
        else:
            messagebox.showerror("Import failed", msg, parent=self)
