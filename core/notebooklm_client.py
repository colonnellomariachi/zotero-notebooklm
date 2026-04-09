from __future__ import annotations
import asyncio
from pathlib import Path
from loguru import logger

try:
    import notebooklm
    _NLM_AVAILABLE = True
except ImportError:
    _NLM_AVAILABLE = False
    logger.warning("notebooklm-py not installed — NotebookLM features disabled")

from models import NotebookInfo


def _require_nlm():
    if not _NLM_AVAILABLE:
        raise RuntimeError(
            "notebooklm-py is not installed. Run: pip install notebooklm-py"
        )


def _run(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
        # Already inside an event loop (e.g. tests) — use a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        return asyncio.run(coro)


def list_notebooks() -> list[NotebookInfo]:
    _require_nlm()

    async def _list():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            notebooks = await client.notebooks.list()
            return [
                NotebookInfo(
                    notebook_id=nb.id,
                    title=nb.title,
                    source_count=getattr(nb, "sources_count", 0),
                )
                for nb in notebooks
            ]

    return _run(_list())


def create_notebook(title: str) -> str:
    """Create a new notebook and return its ID."""
    _require_nlm()

    async def _create():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            nb = await client.notebooks.create(title)
            return nb.id

    return _run(_create())


def add_sources_to_notebook(notebook_id: str, sources: list[Path | str]) -> bool:
    _require_nlm()

    async def _add():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            for source in sources:
                path = Path(source)
                logger.debug(f"Uploading {path.name} to notebook {notebook_id}")
                await client.sources.add_file(notebook_id, path, wait=True)
        return True

    try:
        return _run(_add())
    except Exception as e:
        logger.error(f"Error adding sources to notebook {notebook_id}: {e}")
        return False


def add_context_note(notebook_id: str, markdown_text: str) -> bool:
    _require_nlm()

    async def _add():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            await client.sources.add_text(
                notebook_id,
                title="Collection Metadata",
                content=markdown_text,
            )
        return True

    try:
        return _run(_add())
    except Exception as e:
        logger.error(f"Error adding context note to notebook {notebook_id}: {e}")
        return False


def upload_and_annotate(
    notebook_id: str,
    sources: list[Path | str],
    context_note: str | None = None,
    on_progress=None,
) -> bool:
    """
    Upload sources and optionally add a context note in a single session.
    Replaces separate add_sources_to_notebook + add_context_note calls.
    """
    _require_nlm()

    def log(msg: str):
        logger.debug(msg)
        if on_progress:
            on_progress(msg)

    async def _do():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            for source in sources:
                path = Path(source)
                log(f"  Uploading {path.name}...")
                await client.sources.add_file(notebook_id, path, wait=True)
            if context_note:
                await client.sources.add_text(
                    notebook_id,
                    title="Collection Metadata",
                    content=context_note,
                )
        return True

    try:
        return _run(_do())
    except Exception as e:
        logger.error(f"Error in upload_and_annotate for {notebook_id}: {e}")
        return False


def query_notebook(notebook_id: str, prompt: str) -> str:
    _require_nlm()

    async def _query():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            result = await client.chat.ask(notebook_id, prompt)
            return result.answer if hasattr(result, "answer") else str(result)

    return _run(_query())


def export_notebook_notes(notebook_id: str) -> list[str]:
    _require_nlm()

    async def _export():
        async with await notebooklm.NotebookLMClient.from_storage() as client:
            notes = await client.notes.list(notebook_id)
            return [n.content for n in notes if n.content]

    return _run(_export())
