"""Groq Llama-3.3 cleanup — free tier, ~100ms response, no extra SDK needed."""

import requests
from config import get_key

_URL   = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.3-70b-versatile"   # best free model on Groq

_SYSTEM = (
    "You are a speech-to-text post-processor. "
    "Return ONLY the cleaned text — no preamble, no quotes, no explanation."
)

_USER = """\
Clean up this speech transcription:
- Fix punctuation, capitalisation, and sentence structure
- Remove filler words and verbal tics: um, uh, like, you know, so, basically, \
right, I mean, kind of, sort of, actually, literally
- Fix obvious transcription errors (homophones, mishears)
- Output natural written-register prose
- Preserve intent and meaning exactly — do NOT add or remove content
- If already clean, return it unchanged

Transcription: {text}"""


def cleanup(text):
    """Return Groq-cleaned text, or the original transcript on any API error."""
    if not text or len(text.split()) < 2:
        return text

    api_key = get_key("groq")
    if not api_key:
        return text  # graceful fallback — raw transcript still works

    try:
        resp = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": _MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user",   "content": _USER.format(text=text)},
                ],
                "temperature": 0.1,
                "max_tokens":  512,
            },
            timeout=15,
        )
        resp.raise_for_status()
        cleaned = resp.json()["choices"][0]["message"]["content"].strip()
        return cleaned if cleaned else text
    except Exception:
        return text     # graceful fallback — raw DeepGram transcript still works
