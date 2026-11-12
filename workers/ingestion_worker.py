from database.models import Document, Job
from repository.job_repository import JobRepository
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime, timezone, timedelta
from services.ingestion_service import IngestionService
import asyncio
import logging

logger = logging.getLogger(__name__)


def claim_next_job(session_factory: sessionmaker[Session]):

    with session_factory.begin() as db:

        now = datetime.now(timezone.utc)

        job_repository = JobRepository(db)

        job = job_repository.get_pending_job(now)

        if job is None:
            return None

        if job.attempts >= job.max_attempts:

            job.status = "FAILED"
            job.error_message = "Maximum attempts exceeded."
            job.completed_at = now

            return None

        document = db.get(Document, job.document_record_id)

        if document is None:

            job.status = "FAILED"
            job.error_message = "Document record not found."
            job.completed_at = now

            return None

        job.status = "RUNNING"
        job.attempts += 1
        job.started_at = now

        document.status = "PROCESSING"

        payload = {
            "job_id": job.job_id,
            "document_id": document.document_id,
            "file_path": document.file_path,
            "filename": document.filename,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts
        }

        return payload


async def worker(
    ingestion_service: IngestionService,
    session_factory,
    stop_event
):

    logger.info("Ingestion worker started")

    while not stop_event.is_set():

        try:

            payload = await asyncio.to_thread(
                claim_next_job,
                session_factory
            )

            if payload is None:

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=1
                    )
                except asyncio.TimeoutError:
                    pass

                continue

            try:

                await asyncio.to_thread(
                    ingestion_service.ingest_pdf,
                    payload["file_path"],
                    payload["document_id"],
                    payload["filename"]
                )

            except Exception as exc:

                logger.exception(
                    "Ingestion failed for job %s",
                    payload["job_id"]
                )

                await asyncio.to_thread(
                    mark_job_failed,
                    session_factory,
                    payload["job_id"],
                    payload["document_id"],
                    str(exc)
                )

            else:
                await asyncio.to_thread(
                    mark_job_success,
                    session_factory,
                    payload["job_id"],
                    payload["document_id"]
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Unexpected worker error")
            await asyncio.sleep(1)


def mark_job_success(
    session_factory: sessionmaker[Session],
    job_id: str,
    document_id: str
):

    with session_factory.begin() as db:

        job = db.get(Job, job_id)
        document = db.query(Document).filter(
            Document.document_id == document_id
        ).first()

        if job is None or document is None:
            raise RuntimeError("Job or document record missing")

        job.status = "SUCCEEDED"
        document.status = "READY"

        job.completed_at = datetime.now(timezone.utc)


def mark_job_failed(
    session_factory: sessionmaker[Session],
    job_id: str,
    document_id: str,
    error_message: str
):

    with session_factory.begin() as db:

        job = db.get(Job, job_id)

        if job is None:
            raise RuntimeError("Job record missing")

        document = db.query(Document).filter(
            Document.document_id == document_id
        ).first()

        now = datetime.now(timezone.utc)

        job.error_message = error_message

        if job.attempts < job.max_attempts:

            # Schedule retry.
            delay = min(
                5 * (2 ** (job.attempts - 1)),
                300
            )

            job.status = "PENDING"

            job.available_at = now + timedelta(seconds=delay)

            if document:
                document.status = "PROCESSING"

        else:

            job.status = "FAILED"
            job.completed_at = now

            if document:
                document.status = "FAILED"
