"""
VoiceType configuration — reads API keys from ~/.voicetype/config.json.

On first launch (no config file), shows a macOS dialog asking for keys.
"""

import os
import json

_CONFIG_DIR  = os.path.expanduser("~/.voicetype")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "config.json")


def _load():
    """Load config dict from disk, or return empty dict."""
    if not os.path.exists(_CONFIG_FILE):
        return {}
    try:
        with open(_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(cfg):
    """Write config dict to disk."""
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_key(name):
    """
    Get an API key by name ('deepgram' or 'groq').
    Returns the key string, or None if not configured.
    """
    cfg = _load()
    return cfg.get(name)


def set_key(name, value):
    """Store an API key."""
    cfg = _load()
    cfg[name] = value
    _save(cfg)


def keys_configured():
    """Return True if both API keys are present."""
    cfg = _load()
    return bool(cfg.get("deepgram")) and bool(cfg.get("groq"))


def prompt_for_keys():
    """
    Show macOS dialogs to collect API keys from the user.
    Returns True if both keys were provided, False if cancelled.
    """
    try:
        import subprocess

        def _ask(title, message, default=""):
            result = subprocess.run(
                [
                    "osascript", "-e",
                    f'display dialog "{message}" with title "{title}" '
                    f'default answer "{default}" buttons {{"Cancel", "OK"}} '
                    f'default button "OK"',
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return None
            # Parse "button returned:OK, text returned:the_key"
            output = result.stdout.strip()
            for part in output.split(", "):
                if part.startswith("text returned:"):
                    return part[len("text returned:"):].strip()
            return None

        # Show welcome message
        subprocess.run(
            [
                "osascript", "-e",
                'display dialog "Welcome to VoiceType!\\n\\n'
                'You need two free API keys to get started:\\n'
                '1. DeepGram (speech-to-text) - deepgram.com\\n'
                '2. Groq (text cleanup) - groq.com\\n\\n'
                'Both have generous free tiers." '
                'with title "VoiceType Setup" '
                'buttons {"Continue"} default button "Continue" '
                'with icon note',
            ],
            capture_output=True, timeout=120,
        )

        # Ask for DeepGram key
        dg_key = _ask(
            "VoiceType Setup (1/2)",
            "Enter your DeepGram API key:\\n\\n"
            "Get one free at console.deepgram.com"
        )
        if not dg_key:
            return False

        # Ask for Groq key
        groq_key = _ask(
            "VoiceType Setup (2/2)",
            "Enter your Groq API key:\\n\\n"
            "Get one free at console.groq.com"
        )
        if not groq_key:
            return False

        # Save both
        cfg = _load()
        cfg["deepgram"] = dg_key
        cfg["groq"] = groq_key
        _save(cfg)

        subprocess.run(
            [
                "osascript", "-e",
                'display dialog "Setup complete!\\n\\n'
                'Hold Left Option (⌥) to dictate.\\n'
                'Press Escape to cancel." '
                'with title "VoiceType" '
                'buttons {"Get Started"} default button "Get Started" '
                'with icon note',
            ],
            capture_output=True, timeout=120,
        )
        return True

    except Exception as e:
        print(f"[VoiceType] key prompt error: {e}", flush=True)
        return False
