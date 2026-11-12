from sqlalchemy.orm import Session
from sqlalchemy import select
from database.models import Job
from datetime import datetime, timezone


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_pending_job(self, now: datetime):

        return self.db.scalar(
            select(Job)
            .where(
                Job.status == "PENDING",
                Job.available_at <= now
            )
            .order_by(Job.created_at.asc())
            .limit(1)

        )

    def get_job_by_id(self, job_id):
        return (
            self.db.query(Job).where(Job.id == job_id,
                                     Job.available_at < datetime.now()).first()
        )



