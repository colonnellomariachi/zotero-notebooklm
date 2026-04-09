from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class ZoteroCollection(BaseModel):
    key: str
    name: str
    item_count: int = 0
    pdf_count: int = 0


class ZoteroAttachment(BaseModel):
    key: str
    title: str
    path: str
    resolved_path: Optional[Path] = None
    content_type: str = ""


class ZoteroItem(BaseModel):
    key: str
    title: str
    authors: list[str] = []
    year: Optional[str] = None
    abstract: Optional[str] = None
    item_type: str = ""
    attachments: list[ZoteroAttachment] = []


class NotebookInfo(BaseModel):
    notebook_id: str
    title: str
    source_count: int = 0


class SyncResult(BaseModel):
    notebook_id: str
    collection_key: str
    sources_uploaded: int = 0
    files_not_found: int = 0
    items_skipped_no_pdf: int = 0
    errors: list[str] = []
    success: bool = True

    def summary(self) -> str:
        return (
            f"✓ {self.sources_uploaded} sources uploaded, "
            f"{self.files_not_found} files not found, "
            f"{self.items_skipped_no_pdf} skipped (no PDF)"
        )
