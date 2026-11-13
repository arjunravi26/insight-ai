from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from api.schema import (
    RegisterRequest,
    UserResponse,
    TokenResponse
)
from database.database import get_db
from database.models import User
from core.security import (
    hash_password,
    authenticate_user,
    create_access_token,
    get_current_user
)
from repository.user_repository import UserRepository


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db)
):
    user_repository = UserRepository(db=db)
    username = payload.username.strip().lower()
    email = str(payload.email).strip().lower()

    if not username:
        raise HTTPException(
            status_code=422,
            detail="Username cannot be empty."
        )
    existing_user = user_repository.fetch_existing_user(
        username=username, email=email)

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username or email already registered."
        )

    try:

        user = User(username=username, email=email,
                    hashed_password=hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username or email already registered."
        )

    return user


@router.post(
    "/login",
    response_model=TokenResponse
)
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    user = authenticate_user(
        db,
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive."
        )

    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token
    )


@router.get(
    "/me",
    response_model=UserResponse
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user
