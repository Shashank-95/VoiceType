"""
Text injection - writes to clipboard and pastes into the focused app.
Uses multiple strategies with fallbacks:
  1. Accessibility API direct text insertion (most reliable)
  2. CGEvent Cmd+V with session tap
  3. CGEvent Cmd+V with HID tap
  4. osascript keystroke (needs Automation permission)
"""

import time
import subprocess
from AppKit import NSPasteboard, NSPasteboardTypeString, NSWorkspace
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventSetFlags,
    CGEventPost,
    kCGHIDEventTap,
    kCGSessionEventTap,
    kCGEventFlagMaskCommand,
)

# Accessibility API for direct text insertion
try:
    from HIServices import (
        AXUIElementCreateSystemWide,
        AXUIElementCopyAttributeValue,
        AXUIElementSetAttributeValue,
        AXIsProcessTrusted,
        kAXFocusedUIElementAttribute,
        kAXSelectedTextAttribute,
        kAXValueAttribute,
        kAXRoleAttribute,
    )
    _HAS_AX = True
except ImportError:
    _HAS_AX = False
    print("[VoiceType] WARNING: HIServices not available, AX paste disabled", flush=True)


def set_clipboard(text):
    """Copy text to the system clipboard."""
    if not text:
        return False
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    ok = pb.setString_forType_(text, NSPasteboardTypeString)
    print(f"[VoiceType] clipboard set: {ok}", flush=True)
    return ok


def do_paste():
    """Paste clipboard content into the focused app. Tries multiple methods."""

    # Log AX trust status
    if _HAS_AX:
        trusted = AXIsProcessTrusted()
        print(f"[VoiceType] AX process trusted: {trusted}", flush=True)

    # Strategy 1: AX direct text insertion (bypasses keyboard simulation entirely)
    try:
        if _paste_ax_insert():
            print("[VoiceType] paste OK (AX insert)", flush=True)
            return
    except Exception as e:
        print(f"[VoiceType] AX insert failed: {e}", flush=True)

    # Strategy 2: CGEvent Cmd+V with kCGSessionEventTap (None source)
    try:
        if _paste_cgevent_session():
            print("[VoiceType] paste OK (CGEvent session)", flush=True)
            return
    except Exception as e:
        print(f"[VoiceType] CGEvent session failed: {e}", flush=True)

    # Strategy 3: CGEvent Cmd+V with kCGHIDEventTap
    try:
        if _paste_cgevent_hid():
            print("[VoiceType] paste OK (CGEvent HID)", flush=True)
            return
    except Exception as e:
        print(f"[VoiceType] CGEvent HID failed: {e}", flush=True)

    # Strategy 4: osascript (needs Automation permission for System Events)
    try:
        if _paste_osascript():
            print("[VoiceType] paste OK (osascript)", flush=True)
            return
    except Exception as e:
        print(f"[VoiceType] osascript failed: {e}", flush=True)

    print("[VoiceType] WARNING: all paste methods failed", flush=True)


# ── Strategy 1: Accessibility API direct text insertion ──────────────────

def _paste_ax_insert():
    """Insert clipboard text directly into the focused text element via AX API."""
    if not _HAS_AX:
        return False

    if not AXIsProcessTrusted():
        print("[VoiceType] AX: process not trusted", flush=True)
        return False

    # Read text from clipboard
    pb = NSPasteboard.generalPasteboard()
    text = pb.stringForType_(NSPasteboardTypeString)
    if not text:
        print("[VoiceType] AX: clipboard empty", flush=True)
        return False

    # Get the system-wide accessibility element
    sys_wide = AXUIElementCreateSystemWide()

    # Get the currently focused UI element
    err, focused = AXUIElementCopyAttributeValue(
        sys_wide, kAXFocusedUIElementAttribute, None
    )
    if err != 0 or focused is None:
        print(f"[VoiceType] AX: no focused element (err={err})", flush=True)
        return False

    # Log what we found
    err_role, role = AXUIElementCopyAttributeValue(focused, kAXRoleAttribute, None)
    print(f"[VoiceType] AX: focused element role={role}", flush=True)

    # Try setting AXSelectedText (replaces selection, or inserts at cursor)
    err = AXUIElementSetAttributeValue(focused, kAXSelectedTextAttribute, text)
    if err == 0:
        return True

    print(f"[VoiceType] AX: set AXSelectedText failed (err={err})", flush=True)

    # Fallback: try setting AXValue (replaces entire field content)
    # Only do this for text fields, not text areas (to avoid overwriting documents)
    if role in ("AXTextField", "AXSearchField", "AXComboBox"):
        err_val, current = AXUIElementCopyAttributeValue(
            focused, kAXValueAttribute, None
        )
        # Append text to current value
        if err_val == 0 and current is not None:
            new_value = str(current) + str(text)
        else:
            new_value = str(text)

        err = AXUIElementSetAttributeValue(focused, kAXValueAttribute, new_value)
        if err == 0:
            print("[VoiceType] AX: set AXValue OK", flush=True)
            return True
        print(f"[VoiceType] AX: set AXValue failed (err={err})", flush=True)

    return False


# ── Strategy 2: CGEvent with session tap ─────────────────────────────────

def _paste_cgevent_session():
    """Simulate Cmd+V using CGEvents with None source + session event tap."""
    vk_v = 9

    # None source = anonymous event, sometimes more compatible
    ev_down = CGEventCreateKeyboardEvent(None, vk_v, True)
    if ev_down is None:
        print("[VoiceType] CGEvent: create failed (None source)", flush=True)
        return False
    CGEventSetFlags(ev_down, kCGEventFlagMaskCommand)

    ev_up = CGEventCreateKeyboardEvent(None, vk_v, False)
    CGEventSetFlags(ev_up, kCGEventFlagMaskCommand)

    # Post to session tap instead of HID tap
    CGEventPost(kCGSessionEventTap, ev_down)
    time.sleep(0.05)
    CGEventPost(kCGSessionEventTap, ev_up)
    time.sleep(0.05)

    return True


# ── Strategy 3: CGEvent with HID tap ────────────────────────────────────

def _paste_cgevent_hid():
    """Simulate Cmd+V using CGEvents with HID system state source."""
    vk_v = 9

    from Quartz import CGEventSourceCreate, kCGEventSourceStateHIDSystemState
    src = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

    ev_down = CGEventCreateKeyboardEvent(src, vk_v, True)
    if ev_down is None:
        return False
    CGEventSetFlags(ev_down, kCGEventFlagMaskCommand)

    ev_up = CGEventCreateKeyboardEvent(src, vk_v, False)
    CGEventSetFlags(ev_up, kCGEventFlagMaskCommand)

    CGEventPost(kCGHIDEventTap, ev_down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, ev_up)

    return True


# ── Strategy 4: osascript ────────────────────────────────────────────────

def _paste_osascript():
    """Simulate Cmd+V using osascript."""
    result = subprocess.run(
        [
            "osascript", "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        capture_output=True,
        timeout=5,
    )
    if result.returncode != 0:
        err = result.stderr.decode().strip()
        print(f"[VoiceType] osascript error: {err}", flush=True)
    return result.returncode == 0
