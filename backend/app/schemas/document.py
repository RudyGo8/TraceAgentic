'''
@create_time: 2026/02/02
@Author: GeChao
@File: document.py
'''
from typing import Optional

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    filename: str
    file_type: str
    chunk_count: int
    uploaded_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


class DocumentUploadResponse(BaseModel):
    filename: str
    chunks_processed: int
    message: str


class DocumentUploadResult(BaseModel):
    filename: str
    success: bool
    chunks_processed: int = 0
    message: str


class DocumentBatchUploadResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[DocumentUploadResult]
    message: str


class DocumentDeleteResponse(BaseModel):
    filename: str
    chunks_deleted: int
    message: str
