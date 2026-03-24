"""api/routes/health.py — Health and readiness checks."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    service: str = "GyanaDev — AI Guru for Hindu Epics"
    stack: str = "Groq + Qdrant + MongoDB + Sarvam AI"


@router.get("/", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready")
async def readiness() -> dict:
    """Check all service connections."""
    checks: dict[str, str] = {}

    # Qdrant
    try:
        from api.config import get_settings
        from db.qdrant_store import QdrantStore
        s = get_settings()
        store = QdrantStore(url=s.qdrant_url, api_key=s.qdrant_api_key,
                            collection_name=s.qdrant_collection)
        stats = store.get_stats()
        checks["qdrant"] = f"ok ({stats['total_chunks']:,} chunks)"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    # MongoDB
    try:
        from db.mongo_store import MongoStore
        store2 = MongoStore(uri=s.mongodb_uri, db_name=s.mongodb_db)
        store2.close()
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"

    # Groq key
    checks["groq"] = "key_present" if s.groq_api_key.startswith("gsk_") else "invalid_key"

    # Sarvam key
    checks["sarvam"] = "key_present" if s.sarvam_api_key and len(s.sarvam_api_key) > 10 else "missing"

    ok = all("error" not in v and "invalid" not in v and "missing" not in v for v in checks.values())
    return {"status": "ready" if ok else "degraded", "checks": checks}