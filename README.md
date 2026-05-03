# VoiceType

**Voice-to-text for macOS — hold a key, speak, release, text appears.**

A lightweight, Wispr Flow-style voice dictation tool that lives in your menu bar. Hold the Option key, speak naturally, and your words are transcribed, cleaned up, and pasted directly into whatever app you're using.

---

## How It Works

1. **Hold Left Option (⌥)** — recording starts, a floating pill indicator appears with an audio-reactive waveform
2. **Speak naturally** — your voice is captured in real-time
3. **Release Option** — audio is sent to DeepGram for transcription, then Groq cleans up filler words and formatting
4. **Text is pasted** — directly into the focused text field via macOS Accessibility API, and copied to your clipboard as backup

**Press Escape** while recording to cancel.

---

## Features

- **Audio-reactive waveform** — the floating pill indicator responds to your actual voice, not random animations
- **AI-powered cleanup** — removes filler words (um, uh, like, you know), fixes punctuation and capitalisation
- **Direct text injection** — pastes via Accessibility API, no keyboard simulation needed
- **Clipboard backup** — text is always copied to clipboard, even if no text field is focused
- **Menu bar app** — runs silently in the background, no dock icon
- **Auto-start** — can be configured to launch on login
- **Privacy-first** — API keys are stored locally on your machine, never in the source code

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Speech-to-text | [DeepGram](https://deepgram.com) nova-2 |
| Text cleanup | [Groq](https://groq.com) Llama 3.3 70B |
| Menu bar | rumps (Python) |
| Audio capture | sounddevice + PortAudio |
| Text injection | macOS Accessibility API (AXUIElement) |
| UI indicator | AppKit NSWindow + custom NSView drawing |
| Launcher | Embedded Python via C (preserves app bundle identity) |

---

## Installation

### Prerequisites

- **macOS** (Ventura or later recommended)
- **Python 3.9+** (comes with macOS or install from [python.org](https://python.org))
- **Xcode Command Line Tools**:
  ```bash
  xcode-select --install
  ```

### Setup

```bash
# Clone the repo
git clone https://github.com/Shashank-95/VoiceType.git
cd VoiceType

# Run the installer
bash install.sh
```

### First Launch

1. Double-click `VoiceType.app` to launch
2. On first launch, you'll be prompted for two API keys:
   - **DeepGram** — sign up free at [console.deepgram.com](https://console.deepgram.com)
   - **Groq** — sign up free at [console.groq.com](https://console.groq.com)
3. Grant **Accessibility** permission when macOS asks (System Settings > Privacy & Security > Accessibility)
4. Grant **Microphone** access when prompted

### Auto-Start on Login (Optional)

To have VoiceType start automatically when you log in:

System Settings > General > Login Items > add VoiceType.app

---

## Architecture

```
VoiceType.app
  └── Contents/MacOS/VoiceType  (C launcher — embeds Python, preserves app identity)
        └── app.py               (main loop — rumps menu bar + NSEvent monitors)
              ├── audio.py       (microphone capture via sounddevice)
              ├── indicator.py   (floating pill — custom NSView drawing at 60fps)
              ├── transcribe.py  (DeepGram nova-2 REST API)
              ├── cleanup.py     (Groq Llama 3.3 text cleanup)
              ├── inject.py      (AX API text insertion + clipboard)
              └── config.py      (API key management — ~/.voicetype/config.json)
```

The C launcher (`launcher.c`) embeds Python directly into the Mach-O binary rather than spawning a separate Python process. This preserves the app bundle identity so macOS Accessibility permissions are granted to `VoiceType.app`, not to the Python interpreter.

---

## Why Not Just Use Wispr Flow?

Wispr Flow's free tier has strict word limits that cap how much you can dictate. VoiceType uses DeepGram and Groq directly — both offer far more generous free tiers (DeepGram gives $200 in credits, Groq is free for personal use) so you can dictate as much as you want without hitting a paywall. The speed is comparable too — DeepGram nova-2 returns transcriptions in ~300ms and Groq cleans up text in ~100ms, so the full flow completes in under a second.

---

## License

MIT

---

*Built by [Shashank](https://github.com/Shashank-95)*
