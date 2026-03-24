"""
api/config.py — Central settings for GyanaDev.
All modules import from here. Never read os.environ directly.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Groq ──────────────────────────────────────────────────────
    groq_api_key: str = Field(..., description="Groq API key (gsk_...)")
    groq_llm_model: str = "llama-3.3-70b-versatile"
    groq_temperature: float = Field(0.0, ge=0.0, le=1.0)
    groq_max_tokens: int = Field(1024, ge=128, le=4096)

    # ── Qdrant ────────────────────────────────────────────────────
    qdrant_url: str = Field(..., description="Qdrant cluster URL")
    qdrant_api_key: str = Field(..., description="Qdrant API key")
    qdrant_collection: str = "book_chunks"

    # ── MongoDB ───────────────────────────────────────────────────
    mongodb_uri: str = Field(..., description="MongoDB Atlas URI")
    mongodb_db: str = "gyanadeva"

    # ── Sarvam AI ─────────────────────────────────────────────────
    sarvam_api_key: str = Field(..., description="Sarvam AI API key")
    sarvam_stt_model: str = "saaras:v3"
    sarvam_tts_model: str = "bulbul:v3"
    sarvam_tts_pace: float = Field(0.95, ge=0.5, le=2.0)

    # ── Auth ──────────────────────────────────────────────────────
    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # ── RAG ───────────────────────────────────────────────────────
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    hybrid_alpha: float = Field(0.6, ge=0.0, le=1.0)
    min_faithfulness_score: float = Field(0.5, ge=0.0, le=1.0)

    # ── API ───────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── Languages ─────────────────────────────────────────────────
    default_language: str = "en"
    supported_languages: str = "hi,te,ta,kn,ml,mr,bn,gu,pa,or,as,sa,ur"

    @property
    def supported_language_list(self) -> list[str]:
        return [l.strip() for l in self.supported_languages.split(",")]

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("groq_api_key")
    @classmethod
    def validate_groq_key(cls, v: str) -> str:
        if not v.startswith("gsk_"):
            raise ValueError("GROQ_API_KEY must start with 'gsk_'")
        return v

    @field_validator("groq_temperature")
    @classmethod
    def warn_nonzero_temp(cls, v: float) -> float:
        if v > 0.0:
            import warnings
            warnings.warn(
                f"groq_temperature={v}. Use 0.0 to prevent hallucinations.",
                UserWarning, stacklevel=2,
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()