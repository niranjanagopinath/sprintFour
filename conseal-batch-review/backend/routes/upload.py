import asyncio
import io
import uuid
import zipfile
from typing import List, Tuple

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from services.upload_service import process_upload

router = APIRouter(prefix="/documents", tags=["upload"])


class UploadResponse(BaseModel):
    batch_id: str
    uploaded_count: int
    document_ids: List[str]


def _extract_pdfs(filename: str, file_bytes: bytes) -> List[Tuple[str, bytes]]:
    """Return a list of (filename, bytes) for every PDF in the upload.
    Handles plain PDFs and ZIP archives containing PDFs."""
    name_lower = filename.lower()
    if name_lower.endswith(".pdf"):
        return [(filename, file_bytes)]
    if name_lower.endswith(".zip"):
        results = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                for member in zf.namelist():
                    if member.lower().endswith(".pdf") and not member.startswith("__MACOSX"):
                        results.append((member.split("/")[-1], zf.read(member)))
        except zipfile.BadZipFile:
            pass
        return results
    return []


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload PDF files or ZIP archives containing PDFs.

    All PDFs are ingested concurrently (up to 5 run detection at a time).
    The route returns as soon as every file is registered in the DB;
    detection continues in the background.
    """
    if not files:
        raise HTTPException(400, "No files uploaded")

    batch_id = f"batch-{uuid.uuid4().hex[:8]}"

    # Collect every (name, bytes) pair across all uploaded files/zips
    all_pdfs: List[Tuple[str, bytes]] = []
    for file in files:
        file_bytes = await file.read()
        all_pdfs.extend(_extract_pdfs(file.filename, file_bytes))

    if not all_pdfs:
        raise HTTPException(422, "No valid PDF files found in the upload")

    # Process all PDFs concurrently — process_upload inserts the doc record
    # and fires detection as a background task throttled by the semaphore.
    results = await asyncio.gather(
        *[process_upload(name, data, batch_id) for name, data in all_pdfs],
        return_exceptions=True,
    )

    doc_ids = [r for r in results if isinstance(r, str)]
    failed  = [str(r) for r in results if isinstance(r, Exception)]
    if failed:
        import logging
        logging.getLogger(__name__).warning("Upload failures: %s", failed)

    if not doc_ids:
        raise HTTPException(422, "All files failed to process")

    return UploadResponse(
        batch_id=batch_id,
        uploaded_count=len(doc_ids),
        document_ids=doc_ids,
    )
