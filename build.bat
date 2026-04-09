@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  Build script for Zotero ↔ NotebookLM Bridge
REM  Output: dist\ZoteroNotebookLM\ZoteroNotebookLM.exe
REM ─────────────────────────────────────────────────────────────────────────────

echo === Zotero-NotebookLM Build ===
echo.

REM Clean previous build
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
echo [1/3] Cleaned previous build artifacts.

REM Run PyInstaller
echo [2/3] Running PyInstaller...
pyinstaller zotero_notebooklm.spec
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See output above.
    pause
    exit /b 1
)

REM Copy .env.example to dist folder as a reminder
copy .env.example dist\ZoteroNotebookLM\.env.example >nul 2>&1

echo.
echo [3/3] Done!
echo.
echo Output folder: dist\ZoteroNotebookLM\
echo Executable:    dist\ZoteroNotebookLM\ZoteroNotebookLM.exe
echo.
echo IMPORTANT: Before running the .exe for the first time, make sure you have
echo authenticated with Google by running:
echo     notebooklm login
echo This stores your session in %%USERPROFILE%%\.notebooklm\storage_state.json
echo and only needs to be done once (or when the session expires).
echo.
pause
