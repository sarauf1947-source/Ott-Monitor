# -*- coding: utf-8 -*-
"""Auth and user management routes. api/auth/auth_routes.py"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.auth_utils import (
    verify_password, hash_password,
    create_access_token, create_refresh_token,
    verify_token, ACCESS_TOKEN_EXPIRE_MINUTES,
)
from api.auth.auth_schemas import (
    LoginRequest, TokenResponse, RefreshRequest,
    UserCreate, UserUpdate, UserPasswordReset, UserResponse,
)
from api.auth.auth_deps import get_current_user, require_admin
from db.database import get_db

auth_router  = APIRouter(prefix="/api/v1/auth",  tags=["Authentication"])
users_router = APIRouter(prefix="/api/v1/users", tags=["User Management"])


def _fmt(u) -> UserResponse:
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at.isoformat(),
        last_login=u.last_login.isoformat() if u.last_login else None,
    )


# Login
@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    from db.models import User
    result = await db.execute(select(User).where(User.username == payload.username))
    user   = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Account is disabled")
    user.last_login = datetime.utcnow()
    await db.flush()
    return TokenResponse(
        access_token=create_access_token({"sub": user.username, "role": user.role}),
        refresh_token=create_refresh_token({"sub": user.username}),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_fmt(user),
    )


# Refresh token
@auth_router.post("/refresh")
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from db.models import User
    data   = verify_token(payload.refresh_token, token_type="refresh")
    result = await db.execute(
        select(User).where(User.username == data["sub"], User.is_active == True)  # noqa: E712
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid refresh token")
    return {
        "access_token": create_access_token({"sub": user.username, "role": user.role}),
        "token_type":   "bearer",
        "expires_in":   ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# Current user
@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return _fmt(current_user)


# Change own password
@auth_router.post("/change-password")
async def change_password(
    payload: UserPasswordReset,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.hashed_password = hash_password(payload.new_password)
    await db.flush()
    return {"message": "Password updated successfully"}


# User management (admin only)
@users_router.get("/", response_model=List[UserResponse])
async def list_users(_a=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from db.models import User
    result = await db.execute(select(User).order_by(User.id))
    return [_fmt(u) for u in result.scalars().all()]


@users_router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    payload: UserCreate,
    _a=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from db.models import User
    if (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    if (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=payload.username, email=payload.email,
        full_name=payload.full_name, role=payload.role,
        is_active=payload.is_active,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _fmt(user)


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _a=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from db.models import User
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return _fmt(user)


@users_router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    payload: UserPasswordReset,
    _a=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from db.models import User
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.hashed_password = hash_password(payload.new_password)
    await db.flush()
    return {"message": f"Password reset for '{user.username}'"}


@users_router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from db.models import User
    if current_admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    return {"message": f"User '{user.username}' deleted"}
