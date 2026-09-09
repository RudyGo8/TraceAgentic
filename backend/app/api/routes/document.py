import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.models.db_user import User
from app.schemas.auth import (
    DocumentBatchUploadResponse,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentUploadResponse,
    DocumentUploadResult,
)
from app.core.security import require_admin
from app.utils.log import get_logger
from app.services.milvus_service import milvus_service
from app.services.milvus_writer import milvus_writer

logger = get_logger(__name__)

router_r1 = APIRouter(
    prefix="/api/r1/documents",
    tags=["documents"],
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
UPLOAD_DIR = DATA_DIR / "documents"
ALLOWED_EXTENSIONS = (".pdf", ".docx", ".doc", ".xlsx", ".xls")

# 清理文件名
def _sanitize_filename(raw_name: str) -> str:
    name = (raw_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="filename is required")
    safe_name = Path(name).name.strip()
    if safe_name != name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="invalid filename")
    return safe_name


def _validate_supported_file(filename: str) -> None:
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only PDF, Word, and Excel documents are supported")


def _escape_milvus_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')

# 写入 milvus
def _write_upload_to_milvus(file_path: Path, filename: str) -> int:
    return milvus_writer.write_documents(str(file_path), filename)


@router_r1.get("", response_model=DocumentListResponse)
async def list_documents(_: User = Depends(require_admin)):
    try:
        milvus_service.init_collection()
        results = milvus_service.query(output_fields=["filename", "file_type"], limit=10000)

        file_stats = {}
        for item in results:
            filename = item.get("filename", "")
            file_type = item.get("file_type", "")
            if filename not in file_stats:
                file_stats[filename] = {"filename": filename, "file_type": file_type, "chunk_count": 0}
            file_stats[filename]["chunk_count"] += 1

        documents = [DocumentInfo(**stats) for stats in file_stats.values()]
        return DocumentListResponse(documents=documents)
    except Exception as e:
        logger.exception("Failed to load document list")
        raise HTTPException(status_code=500, detail=f"Failed to load document list: {str(e)}")

# 上传接口
@router_r1.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), _: User = Depends(require_admin)):
    filename = _sanitize_filename(file.filename or "")
    _validate_supported_file(filename)

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = UPLOAD_DIR / filename
        with open(file_path, "wb") as f:
            f.write(await file.read())

        chunk_count = _write_upload_to_milvus(file_path, filename)
        return DocumentUploadResponse(
            filename=filename,
            chunks_processed=chunk_count,
            message=f"Uploaded {filename}, processed {chunk_count} chunks",
        )
    except Exception as e:
        logger.exception("Document upload failed: %s", filename)
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")


@router_r1.post("/batch-upload", response_model=DocumentBatchUploadResponse)
async def batch_upload_document(files: list[UploadFile] = File(...), _: User = Depends(require_admin)):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    results: list[DocumentUploadResult] = []

    for file in files:
        filename = file.filename or "unknown"
        try:
            filename = _sanitize_filename(filename)
            _validate_supported_file(filename)

            file_path = UPLOAD_DIR / filename
            with open(file_path, "wb") as f:
                f.write(await file.read())

            chunk_count = _write_upload_to_milvus(file_path, filename)
            results.append(DocumentUploadResult(
                filename=filename,
                success=True,
                chunks_processed=chunk_count,
                message=f"Uploaded {filename}, processed {chunk_count} chunks",
            ))
        except HTTPException as e:
            results.append(DocumentUploadResult(
                filename=filename,
                success=False,
                chunks_processed=0,
                message=str(e.detail),
            ))
        except Exception as e:
            logger.exception("Batch upload failed for: %s", filename)
            results.append(DocumentUploadResult(
                filename=filename,
                success=False,
                chunks_processed=0,
                message=str(e),
            ))

    succeeded = sum(1 for item in results if item.success)
    failed = len(results) - succeeded
    return DocumentBatchUploadResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
        message=f"Batch upload completed: {succeeded} succeeded, {failed} failed",
    )


@router_r1.delete("/{filename}", response_model=DocumentDeleteResponse)
async def delete_document(filename: str, _: User = Depends(require_admin)):
    try:
        safe_filename = _sanitize_filename(filename)
        milvus_service.init_collection()
        delete_expr = f'filename == "{_escape_milvus_string(safe_filename)}"'
        result = milvus_service.delete(delete_expr)

        return DocumentDeleteResponse(
            filename=safe_filename,
            chunks_deleted=result.get("delete_count", 0) if isinstance(result, dict) else 0,
            message=f"Deleted vector data for {safe_filename}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Document delete failed: %s", filename)
        raise HTTPException(status_code=500, detail=f"Document delete failed: {str(e)}")
