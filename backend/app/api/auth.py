from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user , get_current_admin

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

from app.services.audit_service import create_audit_log

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

import uuid

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
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
            detail="Archivist role is not configured",
        )

    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role_id=archivist_role.id,
        is_active=True,
    )

    db.add(user)

    create_audit_log(
    db,
    user=current_admin,
    action="USER_CREATED",
    entity_type="USER",
    entity_id=user.id,
    description=(
        f"L'administrateur '{current_admin.username}' "
        f"a créé l'archiviste '{user.username}'."
    ),
    details={
        "username": user.username,
        "email": user.email,
        "role": archivist_role.name,
    },
)
    
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



@router.get(
    "/users",
    response_model=list[UserResponse],
)
def get_users(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    users = db.scalars(
        select(User)
        .order_by(User.created_at.desc())
    ).all()

    result = []

    for user in users:
        role = db.get(Role, user.role_id)

        result.append(
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": role.name if role else "UNKNOWN",
                "is_active": user.is_active,
            }
        )

    return result


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
)
def update_user_status(
    user_id: uuid.UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    user = db.get(
        User,
        user_id,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    role = db.get(
        Role,
        user.role_id,
    )

    if not role or role.name != "ARCHIVIST":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only archivists can be managed here",
        )

    old_status = user.is_active

    user.is_active = is_active

    create_audit_log(
    db,
    user=current_admin,
    action="USER_STATUS_CHANGED",
    entity_type="USER",
    entity_id=user.id,
    description=(
        f"L'administrateur '{current_admin.username}' "
        f"a modifié le statut de l'archiviste '{user.username}' "
        f"de {'actif' if old_status else 'inactif'} "
        f"à {'actif' if is_active else 'inactif'}."
    ),
    details={
        "username": user.username,
        "old_status": old_status,
        "new_status": is_active,
    },
)

    

    db.commit()
    db.refresh(user)

    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": role.name,
        "is_active": user.is_active,
    }
