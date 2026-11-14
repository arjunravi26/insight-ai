from api.schema import (
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse)
from fastapi import status
from services.generation_service import GenerationService
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Depends
from starlette.concurrency import run_in_threadpool
from core.security import get_current_user
from database.database import get_db
from database.models import User, Document, Job
from repository.document_repository import DocumentRepository
import aiofiles
import asyncio
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Knowledge"]
)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


MODEL_MAPPING = {
    "Gemini": "Gemini",
    "Mistral": "Mistral",
    "Groq": "Groq",
}


async def remove_files(path: Path | None):
    if path is None:
        return

    await asyncio.to_thread(
        path.unlink,
        missing_ok=True

    )

async def save_document(file: UploadFile, file_path: str, temp_path):

    chunk_len = 0

    async with aiofiles.open(temp_path, "wb") as desitination:
        while chunk := await file.read(1024 * 1024):
            chunk_len += len(chunk)
            if chunk_len > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, detail="PDF exceeds the 20 MB limit.")
            await desitination.write(chunk)

    async with aiofiles.open(temp_path, "rb") as pdf:
        if await pdf.read(5) != b"%PDF-":
            raise HTTPException(status_code=400, detail="Invalid PDF file")

@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file_path: Path | None = None
    temp_path: Path | None = None
    document_record_created = False
    document_id = None


    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported."
            )

        document_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        filename = Path(file.filename.replace("\\", "/")).name

        temp_path = UPLOAD_DIR / F"{document_id}.temp"
        file_path = UPLOAD_DIR / f"{document_id}.pdf"

        document_repository = DocumentRepository(db=db)

        await save_document(file=file, file_path=file_path, temp_path=temp_path)

        await asyncio.to_thread(
            os.replace,
            temp_path,
            file_path
        )
        temp_path = None

        try:
            document = Document(
                document_id=document_id, user_id=current_user.id, filename=filename, file_path=str(file_path), status="PROCESSING")
            db.add(document)
            db.flush()
            job = Job(job_id=job_id, user_id=current_user.id,
                      document_record_id=document.id, job_type="INGESTION", status="PENDING")
            db.add(job)
            db.commit()
            document_record_created = True
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Unable to create document record"
            )

        return DocumentUploadResponse(
            document_id=document_id,
            job_id=job_id,
            filename=filename,
            document_status="PROCESSING",
            job_status="PENDING",
            message="Document uploaded. Ingestion has been queued.",
            created_at=datetime.now(timezone.utc)
        )

    except HTTPException:
        db.rollback()
        await remove_files(path=temp_path)

        if not document_record_created:
            await remove_files(path=file_path)
        raise

    except IntegrityError:
        db.rollback()
        await remove_files(path=temp_path)

        if not document_record_created:
            await remove_files(path=file_path)
        logger.exception(
            f"Database document record creation failed %s.", document_id)

        try:
            document_repository.update_status(
                user_id=current_user.id, document_id=document_id, status="FAILED")
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                f"Could not update document status %s.", document_id)
        raise HTTPException(status_code=409, detail="Unable to save document.")

    except Exception:
        db.rollback()
        await remove_files(temp_path)

        if document_record_created:

            logger.exception("Document ingestion failed")

            try:
                document_repository.update_status(
                    user_id=current_user.id, document_id=document_id, status="FAILED")
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    f"Could not update document status %s.", document_id)
        else:
            await remove_files(file_path)

        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed."
        )

    finally:
        await file.close()


@router.post(
    "/chat",
    response_model=ChatResponse
)
async def chat(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    query = payload.query.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty."
        )
    try:
        document_repository = DocumentRepository(db=db)
        document = document_repository.get_owned_document(
            document_id=payload.document_id,
            user_id=current_user.id
        )

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found."
            )

        if document.status != "READY":
            raise HTTPException(
                status_code=409,
                detail="Document is not ready for querying."
            )

        generation_service: GenerationService = request.app.state.generation_service

        provider = MODEL_MAPPING[payload.model]
        follow_ups = []

        answer, follow_ups = await run_in_threadpool(
            generation_service.generate_response,
            provider=provider,
            query=query,
            document_id=payload.document_id,
            user_id=current_user.id
        )

        return ChatResponse(
            answer=answer,
            follow_ups=follow_ups[:3] if follow_ups else []
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except Exception:
        logger.exception("Chat generation failed")

        raise HTTPException(
            status_code=500,
            detail="Unable to generate an answer."
        )


@router.get("/documents")
async def get_user_documents(current_user=Depends(get_current_user), db: Session = Depends(get_db)):

    document_repository = DocumentRepository(db)
    documents = document_repository.get_user_documents(current_user.id)

    return [
        {
            "document_id": doc.document_id,
            "filename": doc.filename,
            "status": doc.status
        }
        for doc in documents
    ]
