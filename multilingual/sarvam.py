"""
multilingual/sarvam.py — Sarvam AI voice pipeline.
Saaras v3 (STT) + Bulbul v3 (TTS) for 22 Indian languages.
"""
from __future__ import annotations
import base64, io, logging, re, requests
import aiohttp

logger = logging.getLogger(__name__)


def _detect_audio_mime(data: bytes) -> str:
    """Detect audio format from magic bytes."""
    if data[:4] == b"RIFF":
        return "audio/wav"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[:4] in (b"\x1aE\xdf\xa3", b"\x1aE\xdf\xa3"):
        return "audio/webm"
    # WebM also starts with these bytes
    if len(data) > 4 and data[0:4] == bytes([0x1a, 0x45, 0xdf, 0xa3]):
        return "audio/webm"
    # Default to webm (what browsers record)
    return "audio/webm"

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"

ISO_TO_BCP47 = {
    "hi": "hi-IN", "te": "te-IN", "ta": "ta-IN", "kn": "kn-IN",
    "ml": "ml-IN", "mr": "mr-IN", "bn": "bn-IN", "gu": "gu-IN",
    "pa": "pa-IN", "or": "od-IN", "as": "as-IN", "sa": "sa-IN",
    "ur": "ur-IN", "en": "en-IN",
}
BCP47_TO_ISO = {v: k for k, v in ISO_TO_BCP47.items()}

DEFAULT_VOICES = {
    "hi": "meera", "te": "pavithra", "ta": "maitreyi",
    "kn": "diya", "ml": "iniya", "mr": "aarohi",
    "bn": "ria", "gu": "ananya", "pa": "amol",
    "or": "arjun", "en": "meera",
}
TTS_SUPPORTED = set(DEFAULT_VOICES.keys())


class SarvamSTT:
    def __init__(self, api_key: str, model: str = "saaras:v3", mode: str = "transcribe"):
        self.api_key = api_key
        self.model = model
        self.mode = mode

    def transcribe(self, audio_bytes: bytes, language: str | None = None) -> tuple[str, str]:
        lang_code = ISO_TO_BCP47.get(language, "unknown") if language and language != "auto" else "unknown"
        headers = {"api-subscription-key": self.api_key}
        # Detect format from magic bytes
        mime = _detect_audio_mime(audio_bytes)
        fname = "audio.webm" if "webm" in mime else "audio.wav" if "wav" in mime else "audio.ogg"
        files = {"file": (fname, audio_bytes, mime)}
        data = {"model": self.model, "language_code": lang_code, "mode": self.mode}
        r = requests.post(SARVAM_STT_URL, headers=headers, files=files, data=data, timeout=30)
        r.raise_for_status()
        result = r.json()
        text = result.get("transcript", "")
        detected = BCP47_TO_ISO.get(result.get("language_code", "en-IN"), "en")
        return text, detected

    async def transcribe_async(self, audio_bytes: bytes, language: str | None = None) -> tuple[str, str]:
        lang_code = ISO_TO_BCP47.get(language, "unknown") if language and language != "auto" else "unknown"
        headers = {"api-subscription-key": self.api_key}
        mime = _detect_audio_mime(audio_bytes)
        fname = "audio.webm" if "webm" in mime else "audio.wav" if "wav" in mime else "audio.ogg"
        form = aiohttp.FormData()
        form.add_field("file", audio_bytes, filename=fname, content_type=mime)
        form.add_field("model", self.model)
        form.add_field("language_code", lang_code)
        form.add_field("mode", self.mode)
        async with aiohttp.ClientSession() as s:
            async with s.post(SARVAM_STT_URL, headers=headers, data=form,
                              timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                result = await resp.json()
        text = result.get("transcript", "")
        detected = BCP47_TO_ISO.get(result.get("language_code", "en-IN"), "en")
        return text, detected


class SarvamTTS:
    def __init__(self, api_key: str, model: str = "bulbul:v3", pace: float = 0.95):
        self.api_key = api_key
        self.model = model
        self.pace = pace

    def synthesise(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        if language not in TTS_SUPPORTED:
            language = "en"
        target_lang = ISO_TO_BCP47.get(language, "en-IN")
        speaker = voice or DEFAULT_VOICES.get(language, "meera")
        chunks = self._chunk_text(text)
        all_audio = b""
        headers = {"api-subscription-key": self.api_key, "Content-Type": "application/json"}
        for chunk in chunks:
            payload = {
                "inputs": [chunk], "target_language_code": target_lang,
                "speaker": speaker, "model": self.model,
                "pace": self.pace, "enable_preprocessing": True,
            }
            r = requests.post(SARVAM_TTS_URL, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            audios = r.json().get("audios", [""])
            if audios[0]:
                all_audio += base64.b64decode(audios[0])
        return all_audio

    async def synthesise_async(self, text: str, language: str = "en", voice: str | None = None) -> bytes:
        if language not in TTS_SUPPORTED:
            language = "en"
        target_lang = ISO_TO_BCP47.get(language, "en-IN")
        speaker = voice or DEFAULT_VOICES.get(language, "meera")
        chunks = self._chunk_text(text)
        all_audio = b""
        headers = {"api-subscription-key": self.api_key, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                payload = {
                    "inputs": [chunk], "target_language_code": target_lang,
                    "speaker": speaker, "model": self.model,
                    "pace": self.pace, "enable_preprocessing": True,
                }
                async with session.post(SARVAM_TTS_URL, headers=headers, json=payload,
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    resp.raise_for_status()
                    result = await resp.json()
                    audios = result.get("audios", [""])
                    if audios[0]:
                        all_audio += base64.b64decode(audios[0])
        return all_audio

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 2500) -> list[str]:
        if len(text) <= max_chars:
            return [text]
        sentences = re.split(r"(?<=[।.!?])\s+", text)
        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) + 1 <= max_chars:
                current = f"{current} {s}".strip()
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks or [text[:max_chars]]


class LanguageDetector:
    def detect(self, text: str) -> str:
        script = self._detect_by_script(text)
        if script:
            return script
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            return "en"

    @staticmethod
    def _detect_by_script(text: str) -> str | None:
        for ch in text:
            if ch.isspace():
                continue
            cp = ord(ch)
            if 0x0900 <= cp <= 0x097F: return "hi"
            if 0x0C00 <= cp <= 0x0C7F: return "te"
            if 0x0B80 <= cp <= 0x0BFF: return "ta"
            if 0x0C80 <= cp <= 0x0CFF: return "kn"
            if 0x0D00 <= cp <= 0x0D7F: return "ml"
            if 0x0980 <= cp <= 0x09FF: return "bn"
            if 0x0A80 <= cp <= 0x0AFF: return "gu"
            if 0x0A00 <= cp <= 0x0A7F: return "pa"
            if 0x0B00 <= cp <= 0x0B7F: return "or"
            if 0x0600 <= cp <= 0x06FF: return "ur"
            break
        return None


class SarvamTranslator:
    """Translate between Indian languages using Sarvam Translate API."""
    def __init__(self, api_key: str):
        self.api_key = api_key

    def to_english(self, text: str, source_lang: str) -> str:
        if source_lang == "en":
            return text
        return self._translate(text, ISO_TO_BCP47.get(source_lang, "hi-IN"), "en-IN")

    def from_english(self, text: str, target_lang: str) -> str:
        if target_lang == "en":
            return text
        return self._translate(text, "en-IN", ISO_TO_BCP47.get(target_lang, "hi-IN"))

    def _translate(self, text: str, src: str, tgt: str) -> str:
        try:
            headers = {"api-subscription-key": self.api_key, "Content-Type": "application/json"}
            payload = {
                "input": text, "source_language_code": src,
                "target_language_code": tgt, "model": "mayura:v1",
                "enable_preprocessing": True,
            }
            r = requests.post(SARVAM_TRANSLATE_URL, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            return r.json().get("translated_text", text)
        except Exception as e:
            logger.warning(f"Translation failed: {e}")
            return text