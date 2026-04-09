# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Zotero ↔ NotebookLM Bridge.

Build with:
    pyinstaller zotero_notebooklm.spec

Output: dist/ZoteroNotebookLM/ZoteroNotebookLM.exe
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ── Data files ────────────────────────────────────────────────────────────────
datas = []

# ttkbootstrap: themes (JSON + images) and localization files
datas += collect_data_files("ttkbootstrap")

# notebooklm-py: ships a small data directory
datas += collect_data_files("notebooklm")

# pyzotero: py.typed marker (harmless, keeps the package complete)
datas += collect_data_files("pyzotero")

# ── Hidden imports ─────────────────────────────────────────────────────────────
# Packages that PyInstaller's static analysis may miss due to dynamic imports
hiddenimports = [
    # pydantic v2 uses compiled extensions loaded dynamically
    "pydantic",
    "pydantic.deprecated.decorator",
    "pydantic_core",
    # loguru colour support on Windows
    "loguru",
    "colorama",
    # httpx transports
    "httpx._transports.default",
    "httpx._transports.asgi",
    "httpx._transports.wsgi",
    # anyio backends
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    # pyzotero internals
    "pyzotero.zotero",
    "pyzotero.zotero_errors",
    # feedparser used by pyzotero
    "feedparser",
    "feedparser.api",
    # tkinter (should be auto-detected but be explicit)
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.scrolledtext",
    # ttkbootstrap submodules
    *collect_submodules("ttkbootstrap"),
    # python-dotenv
    "dotenv",
]

# ── Analysis ───────────────────────────────────────────────────────────────────
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Playwright is only used by the `notebooklm login` CLI — not needed at runtime
        "playwright",
        # Test / dev tools
        "pytest",
        "unittest",
        "doctest",
        # Unused heavy stdlib modules
        "email.mime",
        "xml.etree",
        "pydoc",
        "difflib",
        "ftplib",
        "imaplib",
        "poplib",
        "smtplib",
        "telnetlib",
        "turtle",
        "curses",
        "readline",
    ],
    noarchive=False,
    optimize=1,  # remove docstrings/asserts — safe for this app
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir mode: keep DLLs separate for faster startup
    name="ZoteroNotebookLM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                # compress binaries if UPX is installed
    console=False,           # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=None,               # replace with "assets/icon.ico" if you add one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ZoteroNotebookLM",
)
