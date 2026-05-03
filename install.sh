#!/bin/bash
# VoiceType — one-shot installer for macOS
# Run:  bash install.sh
#
# Creates VoiceType.app, prompts for API keys on first launch.
# Prerequisites: macOS, Python 3.9+, Xcode Command Line Tools

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

echo ""
echo "  VoiceType Installer"
echo "  ==================="
echo ""

# ── Xcode Command Line Tools check ──────────────────────────────────────
if ! xcode-select -p &>/dev/null; then
  echo "  Xcode Command Line Tools not found."
  echo "  Installing now (this may take a few minutes)..."
  xcode-select --install
  echo ""
  echo "  After installation completes, run this script again:"
  echo "    bash install.sh"
  exit 0
fi
echo "  [ok] Xcode Command Line Tools"

# ── Python 3 check ──────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo ""
  echo "  Python 3 not found."
  echo "  Install from https://python.org/downloads then re-run this script."
  exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  [ok] Python $PY_VER"

# ── Virtual environment ─────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "  [ok] Virtual environment"

# ── Python packages ─────────────────────────────────────────────────────
echo "  Installing Python packages (this may take a minute)..."
pip install --upgrade pip --quiet 2>/dev/null
pip install -r requirements.txt --quiet 2>/dev/null
echo "  [ok] Python packages"

# ── Find Python framework for embedding ─────────────────────────────────
PY_INCLUDE=""
PY_FRAMEWORK_DIR=""

# Get Python version for framework path
PY_MAJOR_MINOR=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

for base in \
  "/Library/Developer/CommandLineTools/Library/Frameworks" \
  "/Applications/Xcode.app/Contents/Developer/Library/Frameworks"; do
  header="$base/Python3.framework/Versions/$PY_MAJOR_MINOR/Headers/Python.h"
  if [ -f "$header" ]; then
    PY_INCLUDE="$base/Python3.framework/Versions/$PY_MAJOR_MINOR/Headers"
    PY_FRAMEWORK_DIR="$base"
    break
  fi
done

if [ -z "$PY_INCLUDE" ]; then
  echo ""
  echo "  Cannot find Python.h in framework headers."
  echo "  Try: xcode-select --install"
  exit 1
fi
echo "  [ok] Python framework"

# ── Compile the embedded launcher ────────────────────────────────────────
echo "  Compiling launcher..."
APP_DIR="$ROOT/VoiceType.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
mkdir -p "$MACOS_DIR"

cc -o "$MACOS_DIR/VoiceType" \
   "$ROOT/launcher.c" \
   -I"$PY_INCLUDE" \
   -F"$PY_FRAMEWORK_DIR" \
   -framework Python3 \
   -Wl,-rpath,"$PY_FRAMEWORK_DIR" \
   -Wno-deprecated-declarations \
   -O2

echo "  [ok] Binary compiled"

# ── Ensure bundle structure ──────────────────────────────────────────────
mkdir -p "$APP_DIR/Contents/Resources"

cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>VoiceType</string>
    <key>CFBundleDisplayName</key>
    <string>VoiceType</string>
    <key>CFBundleIdentifier</key>
    <string>com.voicetype.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>VoiceType</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>VoiceType needs microphone access to transcribe your speech.</string>
    <key>NSAppleEventsUsageDescription</key>
    <string>VoiceType uses Apple Events to paste transcribed text into other apps.</string>
</dict>
</plist>
PLIST

# ── Ad-hoc code sign ────────────────────────────────────────────────────
echo "  Signing app bundle..."
codesign --force --deep --sign - "$APP_DIR" 2>/dev/null
echo "  [ok] Signed"

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
echo "  Installation complete!"
echo ""
echo "  ====================================="
echo "  GETTING STARTED"
echo "  ====================================="
echo ""
echo "  1. Double-click VoiceType.app to launch"
echo ""
echo "  2. First launch will ask for two free API keys:"
echo "     - DeepGram: console.deepgram.com (speech-to-text)"
echo "     - Groq:     console.groq.com     (text cleanup)"
echo ""
echo "  3. Grant permissions when macOS asks:"
echo "     - Accessibility (required for text pasting)"
echo "     - Microphone (required for voice capture)"
echo ""
echo "  HOW TO USE"
echo "  Hold Left Option key -> speak -> release -> text is pasted"
echo "  Press Escape while recording -> cancel"
echo ""
echo "  ====================================="
echo ""
