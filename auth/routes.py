"""
auth/routes.py — Student registration and login endpoints.

POST /auth/register → create account
POST /auth/login    → get JWT token
GET  /auth/me       → get current student profile
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from api.config import Settings, get_settings
from auth.models import (
    RegisterRequest, LoginRequest, TokenResponse, StudentResponse,
    hash_password, verify_password, create_access_token,
    decode_token, generate_student_id,
)
from db.mongo_store import AsyncMongoStore
from db.schemas import new_student_doc

logger = logging.getLogger(__name__)
router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_mongo: AsyncMongoStore | None = None


def get_mongo(settings: Settings = Depends(get_settings)) -> AsyncMongoStore:
    global _mongo
    if _mongo is None:
        _mongo = AsyncMongoStore(uri=settings.mongodb_uri, db_name=settings.mongodb_db)
    return _mongo


# ── Dependency: get current student from JWT ──────────────────────

async def get_current_student(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> dict:
    student_id = decode_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    student = await mongo.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


# ── Routes ────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    settings: Settings = Depends(get_settings),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> TokenResponse:
    """Register a new student account."""
    # Check if email already exists
    existing = await mongo.get_student_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    student_id = generate_student_id()
    password_hash = hash_password(request.password)
    doc = new_student_doc(
        student_id=student_id,
        name=request.name,
        email=request.email,
        password_hash=password_hash,
        age=request.age,
        preferred_language=request.preferred_language,
    )

    await mongo.create_student(doc)
    logger.info(f"New student registered: {request.name} ({student_id})")

    token = create_access_token(
        student_id=student_id,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return TokenResponse(
        access_token=token,
        student_id=student_id,
        name=request.name,
        preferred_language=request.preferred_language,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    settings: Settings = Depends(get_settings),
    mongo: AsyncMongoStore = Depends(get_mongo),
) -> TokenResponse:
    """Login and get a JWT token."""
    student = await mongo.get_student_by_email(request.email)
    if not student or not verify_password(request.password, student["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(
        student_id=student["student_id"],
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )
    logger.info(f"Student logged in: {student['name']} ({student['student_id']})")

    return TokenResponse(
        access_token=token,
        student_id=student["student_id"],
        name=student["name"],
        preferred_language=student["preferred_language"],
    )


@router.get("/me", response_model=StudentResponse)
async def get_me(
    current_student: dict = Depends(get_current_student),
) -> StudentResponse:
    """Get current student's profile."""
    return StudentResponse(**{
        k: current_student.get(k)
        for k in StudentResponse.model_fields
    })
