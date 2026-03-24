"""
api/routes/audio.py — Voice I/O using Sarvam AI.

POST /api/v1/audio/ask        — Full voice pipeline (audio → Guru → audio)
POST /api/v1/audio/transcribe — Speech → text
POST /api/v1/audio/speak      — Text → speech
GET  /api/v1/audio/voices     — List available voices
"""
from __future__ import annotations
import base64
import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from api.config import Settings, get_settings
from auth.routes import get_current_student
from multilingual.sarvam import SarvamSTT, SarvamTTS, DEFAULT_VOICES, TTS_SUPPORTED
from rag.pipeline import GyanadevaRAGPipeline
from api.routes.guru import get_pipeline

logger = logging.getLogger(__name__)
router = APIRouter()

_stt: SarvamSTT | None = None
_tts: SarvamTTS | None = None


def get_stt(settings: Settings = Depends(get_settings)) -> SarvamSTT:
    global _stt
    if _stt is None:
        _stt = SarvamSTT(api_key=settings.sarvam_api_key, model=settings.sarvam_stt_model)
    return _stt


def get_tts(settings: Settings = Depends(get_settings)) -> SarvamTTS:
    global _tts
    if _tts is None:
        _tts = SarvamTTS(api_key=settings.sarvam_api_key, model=settings.sarvam_tts_model, pace=settings.sarvam_tts_pace)
    return _tts


@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    stt: SarvamSTT = Depends(get_stt),
    current_student: dict = Depends(get_current_student),
) -> dict:
    """Transcribe a voice question to text using Sarvam Saaras v3."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")
    try:
        lang_hint = None if language == "auto" else language
        text, detected = await stt.transcribe_async(audio_bytes, language=lang_hint)
        return {"text": text, "detected_language": detected}
    except Exception as e:
        logger.error(f"STT error: {e}")
        raise HTTPException(500, f"Transcription failed: {e}")


@router.post("/speak")
async def speak(
    text: str = Form(...),
    language: str = Form("en"),
    voice: str | None = Form(None),
    tts: SarvamTTS = Depends(get_tts),
    current_student: dict = Depends(get_current_student),
) -> Response:
    """Convert text to speech using Sarvam Bulbul v3."""
    if not text.strip():
        raise HTTPException(400, "Empty text")
    try:
        audio = await tts.synthesise_async(text, language=language, voice=voice)
        return Response(content=audio, media_type="audio/wav",
                        headers={"Content-Disposition": "inline; filename=answer.wav"})
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(500, f"Speech synthesis failed: {e}")


@router.post("/ask")
async def voice_ask(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    book_filter: str | None = Form(None),
    current_student: dict = Depends(get_current_student),
    pipeline: GyanadevaRAGPipeline = Depends(get_pipeline),
    stt: SarvamSTT = Depends(get_stt),
    tts: SarvamTTS = Depends(get_tts),
) -> dict:
    """
    Full voice pipeline:
      1. Sarvam Saaras v3  → transcribe audio
      2. Guru RAG pipeline  → grounded answer
      3. Sarvam Bulbul v3  → speak the answer
    Returns text + base64 audio.
    """
    # Step 1: Transcribe
    audio_bytes = await audio.read()
    try:
        lang_hint = None if language == "auto" else language
        question, detected_lang = await stt.transcribe_async(audio_bytes, language=lang_hint)
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}")

    # Step 2: RAG
    try:
        resp = await pipeline.answer(
            student_id=current_student["student_id"],
            question=question,
            language=detected_lang,
            book_filter=book_filter or None,
        )
    except Exception as e:
        raise HTTPException(500, f"Guru pipeline failed: {e}")

    # Step 3: TTS
    try:
        audio_out = await tts.synthesise_async(resp.answer, language=detected_lang)
        audio_b64 = base64.b64encode(audio_out).decode()
    except Exception as e:
        logger.warning(f"TTS failed: {e}")
        audio_b64 = ""

    return {
        "question_text": question,
        "question_language": detected_lang,
        "answer_text": resp.answer,
        "answer_audio_base64": audio_b64,
        "sources": resp.sources,
        "is_grounded": resp.is_grounded,
        "pronunciation_correction": resp.pronunciation_correction,
    }


@router.get("/voices")
async def list_voices() -> dict:
    """List available Sarvam voices per language."""
    return {
        "model": "bulbul:v3",
        "supported_languages": list(TTS_SUPPORTED),
        "default_voices": DEFAULT_VOICES,
    }