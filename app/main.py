from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Extraction, get_session, init_db
from app.extractor import ClaudeExtractor, ExtractionError, Extractor
from app.schemas import DocumentType, ExtractionOut
from app.storage import Storage, get_storage


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="LLM Document Extractor", version="1.0.0", lifespan=lifespan)


@lru_cache
def get_extractor() -> Extractor:
    return ClaudeExtractor()


def to_out(row: Extraction) -> ExtractionOut:
    return ExtractionOut(
        id=row.id,
        filename=row.filename,
        document_type=DocumentType(row.document_type),
        status=row.status,
        data=row.data,
        error=row.error,
        created_at=row.created_at,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extractions", response_model=ExtractionOut, status_code=201)
def create_extraction(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
    extractor: Extractor = Depends(get_extractor),
):
    pdf = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(pdf) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(415, "Only PDF files are supported")

    row = Extraction(
        filename=file.filename or "upload.pdf",
        storage_key=storage.save(pdf, file.filename or "upload.pdf"),
        document_type=document_type.value,
    )
    try:
        row.data = extractor.extract(pdf, document_type).model_dump()
        row.status = "succeeded"
    except ExtractionError as e:
        row.status = "failed"
        row.error = str(e)
    session.add(row)
    session.commit()
    return to_out(row)


@app.get("/extractions", response_model=list[ExtractionOut])
def list_extractions(
    document_type: DocumentType | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
):
    stmt = select(Extraction).order_by(Extraction.id.desc()).limit(min(limit, 200))
    if document_type:
        stmt = stmt.where(Extraction.document_type == document_type.value)
    return [to_out(r) for r in session.scalars(stmt)]


@app.get("/extractions/{extraction_id}", response_model=ExtractionOut)
def get_extraction(extraction_id: int, session: Session = Depends(get_session)):
    row = session.get(Extraction, extraction_id)
    if row is None:
        raise HTTPException(404, "Extraction not found")
    return to_out(row)
