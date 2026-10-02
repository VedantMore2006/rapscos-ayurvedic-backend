import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "rapscos_development_jwt_secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = int(os.getenv("JWT_EXPIRATION_DAYS", "30"))
MIN_AUTH_MS = int(os.getenv("MIN_AUTH_MS", "700"))
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "RAP-9U4J-4U5H")

# Password hashing
pwd_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64MB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Pre-computed dummy hash to guarantee constant CPU work on non-existent users
DUMMY_HASH = pwd_hasher.hash("dummy_constant_password_value_for_timing_safety")

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_hasher.hash(password)


import base64
import hashlib
import hmac

def verify_scrypt(plain_password: str, scrypt_salt_b64: str, scrypt_hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(scrypt_salt_b64)
        expected_hash = base64.b64decode(scrypt_hash_b64)
        calculated = hashlib.scrypt(
            plain_password.encode("utf-8"),
            salt=salt,
            n=16384,
            r=8,
            p=1,
            maxmem=64 * 1024 * 1024,
            dklen=32,
        )
        return hmac.compare_digest(calculated, expected_hash)
    except Exception:
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("scrypt$"):
        parts = hashed_password.split("$")
        if len(parts) == 3:
            return verify_scrypt(plain_password, parts[1], parts[2])
        return False
    try:
        return pwd_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def verify_dummy(plain_password: str):
    """Perform dummy hash verification to consume CPU time identically to real verify."""
    try:
        pwd_hasher.verify(DUMMY_HASH, plain_password)
    except Exception:
        pass


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=JWT_EXPIRATION_DAYS))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


async def timing_safe_response(coro):
    """
    Wraps an async operation and guarantees the response takes at least
    MIN_AUTH_MS milliseconds, even if an exception is raised.
    Eliminates timing-based email enumeration.
    """
    start = time.monotonic()
    exc = None
    res = None
    try:
        res = await coro
    except Exception as e:
        exc = e
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        remaining_ms = MIN_AUTH_MS - elapsed_ms
        if remaining_ms > 0:
            await asyncio.sleep(remaining_ms / 1000.0)

    if exc is not None:
        raise exc
    return res


def extract_token_from_request(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[str]:
    """
    Extracts token from either:
    1. Authorization: Bearer <token>
    2. Cookie 'rapscos_session' or 'token' (fallback)
    """
    if auth_header and auth_header.credentials:
        return auth_header.credentials

    # Fallback to cookie
    return request.cookies.get("rapscos_token") or request.cookies.get("rapscos_session")


async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(extract_token_from_request),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    user_id = payload.get("sub")
    return db.query(User).filter(User.id == user_id).first()


async def get_current_user(
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user
