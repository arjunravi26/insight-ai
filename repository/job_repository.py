from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import Session

from database.models import Job


class JobRepository:

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def eligible_condition(now):

        return or_(
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

    def fail_exhausted_jobs(self, now):

        eligible = self.eligible_condition(now)

        return self.db.execute(
            update(Job)
            .where(
                eligible,
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

    def claim_next_job(
        self,
        now,
        lease_until,
        lock_token
    ):

        eligible = self.eligible_condition(now)

        candidate_id = (
            select(Job.job_id)
            .where(
                eligible,
                Job.attempts < Job.max_attempts
            )
            .order_by(Job.created_at.asc())
            .limit(1)
            .scalar_subquery()
        )

        stmt = (
            update(Job)
            .where(
                Job.job_id == candidate_id,
                eligible,
                Job.attempts < Job.max_attempts
            )
            .values(
                status="RUNNING",
                attempts=Job.attempts + 1,
                started_at=now,
                locked_until=lease_until,
                lock_token=lock_token
            )
            .returning(
                Job.job_id,
                Job.document_record_id,
                Job.attempts,
                Job.max_attempts
            )
        )

        return (
            self.db.execute(stmt)
            .mappings()
            .one_or_none()
        )

    def mark_claim_missing_document(
        self,
        job_id,
        lock_token,
        now
    ):

        result = self.db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(
                status="FAILED",
                error_message="Document record not found.",
                completed_at=now,
                locked_until=None,
                lock_token=None
            )
        )

        return result.rowcount == 1

    def renew_lease(
        self,
        job_id,
        lock_token,
        lease_until,
        now
    ):

        result = self.db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(
                locked_until=lease_until
            )
        )

        return result.rowcount == 1

    def mark_succeeded(
        self,
        job_id,
        lock_token,
        now
    ):

        result = self.db.execute(
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
        )

        return result.scalar_one_or_none()

    def get_owned_running_job(
        self,
        job_id,
        lock_token,
        now
    ):

        stmt = (
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
        )

        return (
            self.db.execute(stmt)
            .mappings()
            .one_or_none()
        )

    def transition_failed(
        self,
        job_id,
        lock_token,
        now,
        next_status,
        error_message,
        available_at=None
    ):

        values = {
            "status": next_status,
            "error_message": error_message,
            "locked_until": None,
            "lock_token": None
        }

        if next_status == "PENDING":
            values["available_at"] = available_at
            values["completed_at"] = None
        else:
            values["completed_at"] = now

        result = self.db.execute(
            update(Job)
            .where(
                Job.job_id == job_id,
                Job.status == "RUNNING",
                Job.lock_token == lock_token,
                Job.locked_until > now
            )
            .values(**values)
        )

        return result.rowcount == 1