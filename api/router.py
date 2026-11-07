from api.schema import (
    ChatRequest,
    ChatResponse,
    DocumentUploadResponse)
from services.ingestion_service import IngestionService
from services.generation_service import GenerationService
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

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


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=201
)
async def upload_document(
    request: Request,
    file: UploadFile = File(...)
):

    file_path = None

    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported."
            )

        document_id = str(uuid.uuid4())
        filename = Path(file.filename).name

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        file_path = UPLOAD_DIR / f"{document_id}.pdf"

        total_size = 0

        # Save upload in chunks.
        with file_path.open("wb") as destination:

            while chunk := await file.read(1024 * 1024):

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="PDF exceeds the 20 MB limit."
                    )

                destination.write(chunk)

        with file_path.open("rb") as pdf:
            if pdf.read(5) != b"%PDF-":
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PDF file."
                )

        ingestion_service: IngestionService = request.app.state.ingestion_service

        result = await run_in_threadpool(
            ingestion_service.ingest_pdf,
            str(file_path),
            document_id=document_id,
            filename=filename
        )

        return DocumentUploadResponse(
            document_id=document_id,
            filename=filename,
            status="completed",
            result=result
        )

    except HTTPException:
        if file_path:
            file_path.unlink(missing_ok=True)
        raise

    except Exception:
        if file_path:
            file_path.unlink(missing_ok=True)

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
    payload: ChatRequest
):

    query = payload.query.strip()

    if not query:
        raise HTTPException(
            status_code=422,
            detail="Query cannot be empty."
        )

    try:
        generation_service: GenerationService = request.app.state.generation_service

        provider = MODEL_MAPPING[payload.model]
        print(f"Provider selected: {provider}")
        follow_ups = []

        answer = await run_in_threadpool(
            generation_service.generate_response,
            provider=provider,
            query=query,
            document_id=payload.document_id,

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
