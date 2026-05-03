"""DeepGram nova-2 transcription via REST API."""

import requests
from config import get_key

_URL = "https://api.deepgram.com/v1/listen"

_PARAMS = {
    "model":        "nova-2",
    "language":     "en-US",
    "smart_format": "true",   # auto-capitalise, format numbers/dates
    "punctuate":    "true",
    "filler_words": "false",  # strip um/uh at ASR level too
    "disfluencies": "false",
}


def transcribe(audio_bytes):
    """Return transcript string, or empty string on no speech detected."""
    api_key = get_key("deepgram")
    if not api_key:
        raise RuntimeError("DeepGram API key not configured")

    resp = requests.post(
        _URL,
        params=_PARAMS,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type":  "audio/wav",
        },
        data=audio_bytes,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    return text.strip()
