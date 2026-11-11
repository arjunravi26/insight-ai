from api.schema import (
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse)
from services.ingestion_service import IngestionService
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
from database.models import User
from repository.document_repository import DocumentRepository
import aiofiles
import asyncio
import os

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["Knowledge"]
)

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"

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
        message_ok=True

    )


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=201
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported."
            )

        file_path = None
        document_record_created = False

        document_id = str(uuid.uuid4())
        filename = Path(file.filename.replace("\\", "/")).name
        document_repository = DocumentRepository(db=db)

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        temp_path = UPLOAD_DIR / F"{document_id}.temp"
        file_path = UPLOAD_DIR / f"{document_id}.pdf"

        total_size = 0

        async with aiofiles.open(temp_path, "wb") as destination:

            while chunk := await file.read(1024 * 1024):

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="PDF exceeds the 20 MB limit."
                    )

                await destination.write(chunk)

        async with aiofiles.open(temp_path, "rb") as pdf:

            if await pdf.read(5) != b"%PDF-":
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PDF file."
                )

        await asyncio.to_thread(
            os.rename,
            temp_path,
            file_path
        )
        temp_path = None

        ingestion_service: IngestionService = request.app.state.ingestion_service

        try:
            document_repository.upload_document(
                document_id=document_id, filename=filename,
                user_id=current_user.id, status="PROCESSSING"
            )
            document_record_created = True
        except IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="Unable to create document record"
            )

        try:

            result = await run_in_threadpool(
                ingestion_service.ingest_pdf,
                str(file_path),
                document_id=document_id,
                filename=filename
            )
        except Exception as e:
            logger.exception(f"Failed to run ingestion worker. {e}")
            document_repository.update(
                user_id=current_user.id, document_id=document_id, status="FAILED")
            raise HTTPException(
                status_code=500,
                detail="Document Ingestion failed."
            )

        document_repository.update(
            user_id=current_user.id, document_id=document_id, status="READY")

        return DocumentUploadResponse(
            document_id=document_id,
            filename=filename,
            status="completed",
            result=result
        )

    except Exception:
        await remove_files(temp_path)

        if not document_record_created:
            await remove_files(file_path)

        logger.exception("Document ingestion failed")

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

        answer = await run_in_threadpool(
            generation_service.generate_response,
            provider=provider,
            query=query,
            document_id=payload.document_id,
            user_id=current_user.id
        )

        return ChatResponse(
            answer=str(answer),
            follow_ups=follow_ups[:3] if follow_ups else []
        )

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
