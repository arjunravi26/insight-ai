from sqlalchemy import update, select, and_, or_
from database.models import Document, Job
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime, timezone, timedelta
from services.ingestion_service import IngestionService
import asyncio
from asyncio import Event
from database.models import Document, Job
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

LEASE_SECONDS = 300


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def claim_next_job(
    session_factory: sessionmaker[Session],
    lease_seconds: int = LEASE_SECONDS
):

    with session_factory.begin() as db:

        now = utc_now()
        lease_deadline = now + timedelta(seconds=lease_seconds)

        eligible_job = or_(
            and_(
                Job.status == "PENDING",
                Job.available_at <= now
            ),
            and_(
                Job.status == "RUNNING",
                or_(
                    Job.locked_until.is_(None),
                    Job.locked_until <= now
                )
            )
        )

        exhausted_ids = db.execute(
            update(Job)
            .where(
                eligible_job,
                Job.attempts >= Job.max_attempts
            )
            .values(
                status="FAILED",
                error_message="Maximum attempts exceeded.",
                completed_at=now,
                locked_until=None,
                lock_token=None
            )
            .returning(Job.document_record_id)
        ).scalars().all()

        if exhausted_ids:
            db.execute(
                update(Document)
                .where(
                    Document.id.in_(exhausted_ids),
                    Document.status == "PROCESSING"
                )
                .values(status="FAILED")
            )

        candidate_id = (
            select(Job.job_id)
            .where(
                eligible_job,
                Job.attempts < Job.max_attempts
            )
            .order_by(Job.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )

        token = str(uuid4())

        stmt = (
            update(Job)
            .where(
                Job.job_id == candidate_id,
                eligible_job,
                Job.attempts < Job.max_attempts
            )
            .values(
                status="RUNNING",
                attempts=Job.attempts + 1,
                started_at=now,
                locked_until=lease_deadline,
                lock_token=token
            )
            .returning(
                Job.job_id,
                Job.document_record_id,
                Job.attempts,
                Job.max_attempts
            )
        )

        claimed = (
            db.execute(stmt)
            .mappings()
            .one_or_none()
        )

        if claimed is None:
            return None

        document = db.get(
            Document,
            claimed["document_record_id"]
        )

        if document is None:

            db.execute(
                update(Job)
                .where(
                    Job.job_id == claimed["job_id"],
                    Job.lock_token == token,
                    Job.status == "RUNNING"
                )
                .values(
                    status="FAILED",
                    error_message="Document record not found.",
                    completed_at=now,
                    locked_until=None,
                    lock_token=None
                )
            )

            return None

        document.status = "PROCESSING"

        return {
            "job_id": claimed["job_id"],
            "document_id": document.document_id,
            "file_path": document.file_path,
            "filename": document.filename,
            "attempts": claimed["attempts"],
            "max_attempts": claimed["max_attempts"],
            "lock_token": token
        }


async def worker(
    ingestion_service: IngestionService,
    session_factory: sessionmaker[Session],
    stop_event: Event
):

    logger.info("Ingestion worker started")

    while not stop_event.is_set():

        try:

            payload = await asyncio.to_thread(
                claim_next_job,
                session_factory,
                LEASE_SECONDS
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

                await ingest_with_heartbeat(
                    ingestion_service,
                    session_factory,
                    payload,
                    LEASE_SECONDS
                )

            except LeaseLostError:
                logger.warning(
                    "Skipping status update for job %s: lease lost",
                    payload["job_id"]
                )
                continue

            except Exception as exc:

                logger.exception(
                    "Ingestion failed for job %s",
                    payload["job_id"]
                )

                try:
                    await asyncio.to_thread(
                        mark_job_failed,
                        session_factory,
                        payload["job_id"],
                        payload["document_id"],
                        payload["lock_token"],
                        str(exc)
                    )

                except LeaseLostError:
                    logger.warning(
                        "Cannot mark job %s failed: lease lost",
                        payload["job_id"]
                    )

            else:

                try:
                    await asyncio.to_thread(
                        mark_job_success,
                        session_factory,
                        payload["job_id"],
                        payload["document_id"],
                        payload["lock_token"]
                    )

                except LeaseLostError:
                    logger.warning(
                        "Cannot mark job %s successful: lease lost",
                        payload["job_id"]
                    )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Unexpected worker error")
            await asyncio.sleep(1)


class LeaseLostError(Exception):
    pass


def mark_job_success(
    session_factory: sessionmaker[Session],
    job_id: str,
    document_id: str,
    lock_token: str
):

    with session_factory.begin() as db:

        now = utc_now()

        result = db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(
                status="SUCCEEDED",
                completed_at=now,
                locked_until=None,
                lock_token=None
            )
            .returning(Job.document_record_id)
        ).mappings().one_or_none()

        if result is None:
            raise LeaseLostError(
                f"Worker no longer owns job {job_id}"
            )

        doc_result = db.execute(
            update(Document)
            .where(
                Document.id == result["document_record_id"],
                Document.document_id == document_id,
                Document.status == "PROCESSING"
            )
            .values(status="READY")
        )

        if doc_result.rowcount != 1:
            raise RuntimeError(
                "Document missing or not in PROCESSING state"
            )


def mark_job_failed(
    session_factory: sessionmaker[Session],
    job_id: str,
    document_id: str,
    lock_token: str,
    error_message: str
):

    with session_factory.begin() as db:

        now = utc_now()

        current = db.execute(
            select(
                Job.document_record_id,
                Job.attempts,
                Job.max_attempts
            )
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
        ).mappings().one_or_none()

        if current is None:
            raise LeaseLostError(
                f"Cannot fail job {job_id}: lease lost"
            )

        should_retry = (
            current["attempts"] < current["max_attempts"]
        )

        delay = min(
            5 * (2 ** (current["attempts"] - 1)),
            300
        )

        next_status = "PENDING" if should_retry else "FAILED"

        values = {
            "status": next_status,
            "error_message": error_message,
            "locked_until": None,
            "lock_token": None
        }

        if should_retry:
            values["available_at"] = (
                now + timedelta(seconds=delay)
            )
        else:
            values["completed_at"] = now

        result = db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(**values)
        )

        if result.rowcount != 1:
            raise LeaseLostError(
                f"Cannot update job {job_id}: lease lost"
            )

        if not should_retry:

            doc_result = db.execute(
                update(Document)
                .where(
                    Document.id == current["document_record_id"],
                    Document.document_id == document_id,
                    Document.status == "PROCESSING"
                )
                .values(status="FAILED")
            )

            if doc_result.rowcount != 1:
                raise RuntimeError(
                    "Document missing or not in PROCESSING state"
                )


def renew_job_lease(
    session_factory: sessionmaker[Session],
    job_id: str,
    lock_token: str,
    lease_seconds: int = LEASE_SECONDS
) -> bool:

    with session_factory.begin() as db:

        now = utc_now()

        result = db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(
                locked_until=now + timedelta(
                    seconds=lease_seconds
                )
            )
        )

        return result.rowcount == 1


async def ingest_with_heartbeat(
    ingestion_service: IngestionService,
    session_factory: sessionmaker[Session],
    payload: dict,
    lease_seconds: int = LEASE_SECONDS
):

    ingestion_task = asyncio.create_task(
        asyncio.to_thread(
            ingestion_service.ingest_pdf,
            payload["file_path"],
            payload["document_id"],
            payload["filename"]
        )
    )

    heartbeat_interval = max(1, lease_seconds // 3)

    while True:

        done, _ = await asyncio.wait(
            {ingestion_task},
            timeout=heartbeat_interval
        )

        if done:
            return await ingestion_task

        try:
            renewed = await asyncio.to_thread(
                renew_job_lease,
                session_factory,
                payload["job_id"],
                payload["lock_token"],
                lease_seconds
            )

        except Exception:
            logger.exception(
                "Failed to renew lease for job %s",
                payload["job_id"]
            )

            try:
                await asyncio.sleep(1)

                renewed = await asyncio.to_thread(
                    renew_job_lease,
                    session_factory,
                    payload["job_id"],
                    payload["lock_token"],
                    lease_seconds
                )

            except Exception:
                logger.exception("Lease renewal retry failed")
                renewed = False

        if not renewed:

            logger.error(
                "Lease lost for job %s",
                payload["job_id"]
            )

            try:
                await ingestion_task
            except Exception:
                logger.exception(
                    "Ingestion thread failed after lease was lost"
                )

            raise LeaseLostError(
                f"Lease lost for job {payload['job_id']}"
            )
