from sqlalchemy.orm import Session
from database.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id):
        return (
            self.db.query(User).filter(
                User.id == user_id
            ).first()
        )

    def fetch_existing_user(self, username, email):
        return self.db.query(User).filter((User.username == username) | (User.email == email)).first()

    def add_user(self, username, email, hashed_password):
        user = User(username=username, email=email,
                    hashed_password=hashed_password)
        self.db.add(user)
