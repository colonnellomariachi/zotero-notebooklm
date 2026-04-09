"""Entry point for the Zotero ↔ NotebookLM Bridge GUI."""
import sys
from loguru import logger

# Configure loguru: stderr + rotating file
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add("zotero_notebooklm.log", rotation="5 MB", retention=3, level="DEBUG")


def main():
    import config  # noqa: F401 — loads .env early

    if not config.ZOTERO_API_KEY or not config.ZOTERO_USER_ID:
        logger.warning(
            "ZOTERO_API_KEY or ZOTERO_USER_ID not set. "
            "Open Settings in the app to configure credentials."
        )

    from gui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
