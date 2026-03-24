"""
api/main.py — GyanaDev FastAPI application.
"""
from __future__ import annotations
import logging
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from api.config import get_settings

settings = get_settings()
structlog.configure(
    processors=[structlog.stdlib.add_log_level, structlog.stdlib.add_logger_name, structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GyanaDev — AI Guru for Hindu Epics",
    description="Personalised AI teacher for Mahabharata, Ramayana & Bhagavad Gita. Groq + Qdrant + MongoDB + Sarvam AI.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=False,
                   allow_methods=["*"],
                   allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Import and register routers
from auth.routes import router as auth_router
from api.routes.guru import router as guru_router
from api.routes.audio import router as audio_router
from api.routes.profile import router as profile_router
from api.routes.health import router as health_router

app.include_router(health_router, prefix="/health",      tags=["Health"])
app.include_router(auth_router,   prefix="/auth",        tags=["Auth"])
app.include_router(guru_router,   prefix="/api/v1/guru", tags=["Guru"])
app.include_router(audio_router,  prefix="/api/v1/audio",tags=["Audio"])
app.include_router(profile_router,prefix="/api/v1/student", tags=["Student"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>GyanaDev — AI Guru</title>
<style>*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#fdf8e8;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border-radius:20px;padding:48px 56px;box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center;max-width:540px;width:90%}
.om{font-size:64px;margin-bottom:16px}.h1{font-size:32px;color:#c45c00;margin-bottom:4px;font-weight:600}
.sub{color:#888;font-size:14px;margin-bottom:28px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
a{display:block;padding:13px 18px;border-radius:12px;text-decoration:none;font-size:13px;font-weight:500;transition:transform .15s}
a:hover{transform:translateY(-2px)}.docs{background:#ff8008;color:#fff}.health{background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}
.ready{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe}.redoc{background:#faf5ff;color:#7e22ce;border:1px solid #e9d5ff}
.badge{margin-top:24px;padding:12px;background:#f0fdf4;border-radius:10px;font-size:13px;color:#16a34a}
.dot{display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}.ep{margin-top:20px;text-align:left;font-size:12px;color:#666}
.ep p{margin:3px 0}.ep code{background:#f3f4f6;padding:2px 5px;border-radius:4px;font-family:monospace}</style>
</head><body><div class="card">
<div class="om">&#x1F549;&#xFE0F;</div>
<div class="h1">GyanaDev &#x1F64F;</div>
<p class="sub">AI Guru &nbsp;&middot;&nbsp; Groq + Qdrant + MongoDB + Sarvam AI</p>
<div class="grid">
  <a class="docs"   href="/docs">&#x1F4D6; Swagger UI</a>
  <a class="health" href="/health">&#x2764;&#xFE0F; Health</a>
  <a class="ready"  href="/health/ready">&#x2705; Readiness</a>
  <a class="redoc"  href="/redoc">&#x1F4DA; ReDoc</a>
</div>
<div class="badge"><span class="dot"></span>API is live &nbsp;&middot;&nbsp; Llama 3.3 70B &nbsp;&middot;&nbsp; 22 Indian languages</div>
<div class="ep">
  <p style="font-weight:600;color:#374151;margin:12px 0 6px">Endpoints:</p>
  <p>&#x2022; <code>POST /auth/register</code> &mdash; Create student account</p>
  <p>&#x2022; <code>POST /auth/login</code> &mdash; Login, get JWT</p>
  <p>&#x2022; <code>POST /api/v1/guru/ask</code> &mdash; Ask the Guru</p>
  <p>&#x2022; <code>POST /api/v1/guru/ask/stream</code> &mdash; Streaming answer</p>
  <p>&#x2022; <code>POST /api/v1/audio/ask</code> &mdash; Full voice pipeline</p>
  <p>&#x2022; <code>GET  /api/v1/student/profile</code> &mdash; Student profile</p>
  <p>&#x2022; <code>GET  /api/v1/student/progress</code> &mdash; Learning progress</p>
</div>
</div></body></html>""", status_code=200)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("🚀 GyanaDev API starting")
    logger.info(f"   LLM  : {settings.groq_llm_model}")
    logger.info(f"   Embed: all-MiniLM-L6-v2 (local)")
    logger.info(f"   VDB  : Qdrant ({settings.qdrant_collection})")
    logger.info(f"   Mem  : MongoDB ({settings.mongodb_db})")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("👋 GyanaDev shutting down")