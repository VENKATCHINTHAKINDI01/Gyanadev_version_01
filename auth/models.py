"""
auth/models.py — Student authentication models and JWT utilities.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field


# ── Pydantic models ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    age: int = Field(..., ge=6, le=18)
    preferred_language: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student_id: str
    name: str
    preferred_language: str


class StudentResponse(BaseModel):
    student_id: str
    name: str
    email: str
    age: int
    preferred_language: str
    preferred_voice: str
    last_book: str
    last_topic: str
    scores: dict
    streak: int


# ── Password utilities ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash password using bcrypt directly (avoids passlib version conflicts)."""
    pwd_bytes = password.encode("utf-8")[:72]  # bcrypt 72-byte hard limit
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT utilities ──────────────────────────────────────────────────

def create_access_token(
    student_id: str,
    secret_key: str,
    algorithm: str = "HS256",
    expire_minutes: int = 10080,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": student_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(token: str, secret_key: str, algorithm: str = "HS256") -> str | None:
    """Decode JWT and return student_id. Returns None if invalid."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def generate_student_id() -> str:
    return str(uuid.uuid4())