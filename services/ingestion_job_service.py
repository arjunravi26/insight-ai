from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from database.models import Document
from repository.job_repository import JobRepository
from repository.document_repository import DocumentRepository
from schemas.ingestion_job import IngestionJobPayload


LEASE_SECONDS = 300


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LeaseLostError(Exception):
    pass


class IngestionJobService:

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        lease_seconds: int = LEASE_SECONDS
    ):

        self.session_factory = session_factory
        self.lease_seconds = lease_seconds

    def claim_next_job(self):

        with self.session_factory.begin() as db:

            job_repo = JobRepository(db)
            document_repo = DocumentRepository(db)

            now = utc_now()

            exhausted_ids = job_repo.fail_exhausted_jobs(now)

            document_repo.mark_processing_ids_failed(
                exhausted_ids
            )

            lock_token = str(uuid4())

            claimed = job_repo.claim_next_job(
                now=now,
                lease_until=now + timedelta(
                    seconds=self.lease_seconds
                ),
                lock_token=lock_token
            )

            if claimed is None:
                return None

            document = document_repo.get_by_record_id(
                claimed["document_record_id"]
            )

            if document is None:

                job_repo.mark_claim_missing_document(
                    claimed["job_id"],
                    lock_token,
                    utc_now()
                )

                return None

            document_repo.set_processing(document)

            return IngestionJobPayload(
                job_id=claimed["job_id"],
                document_id=document.document_id,
                user_id=document.user_id,
                file_path=document.file_path,
                filename=document.filename,
                attempts=claimed["attempts"],
                max_attempts=claimed["max_attempts"],
                lock_token=lock_token
            )

    def renew_lease(self, payload: IngestionJobPayload):

        with self.session_factory.begin() as db:

            job_repo = JobRepository(db)

            now = utc_now()

            return job_repo.renew_lease(
                job_id=payload.job_id,
                lock_token=payload.lock_token,
                lease_until=now + timedelta(
                    seconds=self.lease_seconds
                ),
                now=now
            )

    def mark_job_success(
        self,
        payload: IngestionJobPayload
    ):

        with self.session_factory.begin() as db:

            job_repo = JobRepository(db)
            document_repo = DocumentRepository(db)

            now = utc_now()

            record_id = job_repo.mark_succeeded(
                job_id=payload.job_id,
                lock_token=payload.lock_token,
                now=now
            )

            if record_id is None:
                raise LeaseLostError(
                    f"Lost ownership of job {payload.job_id}"
                )

            updated = document_repo.mark_status(
                record_id=record_id,
                document_id=payload.document_id,
                expected_status="PROCESSING",
                new_status="READY"
            )

            if not updated:
                raise RuntimeError(
                    "Could not mark document as READY"
                )

    def mark_job_failed(
        self,
        payload: IngestionJobPayload,
        error_message: str
    ):

        with self.session_factory.begin() as db:

            job_repo = JobRepository(db)
            document_repo = DocumentRepository(db)

            now = utc_now()

            current = job_repo.get_owned_running_job(
                job_id=payload.job_id,
                lock_token=payload.lock_token,
                now=now
            )

            if current is None:
                raise LeaseLostError(
                    f"Lost ownership of job {payload.job_id}"
                )

            should_retry = (
                current["attempts"] < current["max_attempts"]
            )

            if should_retry:

                delay = min(
                    5 * (2 ** (current["attempts"] - 1)),
                    300
                )

                next_status = "PENDING"

                available_at = now + timedelta(seconds=delay)

            else:

                next_status = "FAILED"
                available_at = None

            updated = job_repo.transition_failed(
                job_id=payload.job_id,
                lock_token=payload.lock_token,
                now=now,
                next_status=next_status,
                error_message=error_message,
                available_at=available_at
            )

            if not updated:
                raise LeaseLostError(
                    f"Lost ownership while failing job {payload.job_id}"
                )

            if not should_retry:

                updated = document_repo.mark_status(
                    record_id=current["document_record_id"],
                    document_id=payload.document_id,
                    expected_status="PROCESSING",
                    new_status="FAILED"
                )

                if not updated:
                    raise RuntimeError(
                        "Could not mark document as FAILED"
                    )