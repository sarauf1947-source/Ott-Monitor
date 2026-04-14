# -*- coding: utf-8 -*-
"""
api/auth/auth_utils.py
JWT token helpers and password hashing.
bcrypt==4.0.1 must be pinned in requirements.txt for passlib compatibility.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status

SECRET_KEY                  = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Lazy-init password context to avoid import-time bcrypt errors
_pwd_context = None


def _get_pwd():
    global _pwd_context
    if _pwd_context is None:
        from passlib.context import CryptContext
        _pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return _pwd_context


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _get_pwd().verify(plain, hashed)
    except Exception:
        return False


def hash_password(password: str) -> str:
    try:
        return _get_pwd().hash(password)
    except Exception as exc:
        # Fallback: use bcrypt directly if passlib has version issues
        try:
            import bcrypt
            return bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
        except Exception:
            raise RuntimeError(f"Password hashing failed: {exc}") from exc


def verify_password_direct(plain: str, hashed: str) -> bool:
    """Fallback verifier using bcrypt directly, bypassing passlib."""
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# -- JWT -----------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    from jose import jwt
    payload = {
        **data,
        "type": "access",
        "exp":  datetime.utcnow() + (
            expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        ),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    from jose import jwt
    payload = {
        **data,
        "type": "refresh",
        "exp":  datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> dict:
    from jose import JWTError, jwt
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != token_type:
            raise exc
        if not payload.get("sub"):
            raise exc
        return payload
    except JWTError:
        raise exc
