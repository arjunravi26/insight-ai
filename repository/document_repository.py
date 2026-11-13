from sqlalchemy.orm import Session
from database.models import Document
from sqlalchemy import update
from sqlalchemy import update
from sqlalchemy.orm import Session

from database.models import Document


class DocumentRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_owned_document(
        self,
        document_id: str,
        user_id: int
    ):

        return (
            self.db.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.user_id == user_id
            )
            .first()
        )

    def get_user_documents(self, user_id: int):
        return (
            self.db.query(Document)
            .filter(
                Document.user_id == user_id,
                Document.status.in_(["READY", "FAILED"])
            )
            .order_by(Document.created_at.desc())
            .all()
        )

    def update_status(self, user_id: int, document_id: str, status: str):
        documents = self.get_owned_document(
            user_id=user_id, document_id=document_id)

        if documents is None:
            return False

        documents.status = status
        self.db.flush()
        return True

    def get_by_record_id(self, record_id):

        return self.db.get(
            Document,
            record_id
        )

    def set_processing(self, document):

        document.status = "PROCESSING"

    def mark_status(
        self,
        record_id,
        document_id,
        expected_status,
        new_status
    ):

        result = self.db.execute(
            update(Document)
            .where(
                Document.id == record_id,
                Document.document_id == document_id,
                Document.status == expected_status
            )
            .values(
                status=new_status
            )
        )

        return result.rowcount == 1

    def mark_processing_ids_failed(self, record_ids):

        if not record_ids:
            return

        self.db.execute(
            update(Document)
            .where(
                Document.id.in_(record_ids),
                Document.status == "PROCESSING"
            )
            .values(status="FAILED")
        )
