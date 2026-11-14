from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models import Document

def get_owned_document(
    db: Session,
    document_id: str,
    user_id: int
):
    document = (
        db.query(Document)
        .filter(
            Document.document_id == document_id,
            Document.user_id == user_id
        )
        .first()
    )

    if not document:
        # Don't reveal whether another user's document exists.
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return document