from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_username = db.scalar(
        select(User).where(User.username == data.username)
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    existing_email = db.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    archivist_role = db.scalar(
        select(Role).where(Role.name == "ARCHIVIST")
    )

    if not archivist_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default role is not configured",
        )

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=archivist_role.id,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": archivist_role.name,
        "is_active": user.is_active,
    }



@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == data.username)
    )

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    access_token = create_access_token(
        subject=str(user.id)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = db.get(Role, current_user.role_id)

    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "role": role.name if role else "UNKNOWN",
        "is_active": current_user.is_active,
    }