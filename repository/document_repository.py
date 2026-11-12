from sqlalchemy.orm import Session
from database.models import Document
from sqlalchemy import update


class DocumentRepository:

    def __init__(self, db: Session):

        self.db = db

    def get_by_document_id(self, document_id: str):

        return (
            self.db.query(Document)
            .filter(
                Document.document_id == document_id
            )
            .first()
        )

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
                Document.status == "READY"
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
