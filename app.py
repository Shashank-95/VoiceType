"""
VoiceType - Wispr Flow-style voice dictation for macOS.

Hold Left Option key  ->  recording starts
Release              ->  DeepGram nova-2 transcribes, Groq/Llama cleans, text is pasted
Press Esc            ->  cancel without pasting

Uses NSEvent global monitors (AppKit) for keyboard input.
"""

import os
import sys
import queue
import threading

# Redirect all output to a log file so we can debug when launched via 'open'
_LOG = open("/tmp/voicetype.log", "w", buffering=1)
sys.stdout = _LOG
sys.stderr = _LOG

import rumps
from AppKit import NSEvent
from Foundation import NSDictionary

from config     import keys_configured, prompt_for_keys
from audio      import AudioCapture
from transcribe import transcribe
from cleanup    import cleanup
from inject     import set_clipboard, do_paste
from indicator  import RecordingIndicator

# -- AppKit event constants --
_MASK_FLAGS    = 1 << 12   # NSEventMaskFlagsChanged
_MASK_KEYDOWN  = 1 << 10   # NSEventMaskKeyDown

_FLAG_OPTION   = 1 << 19   # NSEventModifierFlagOption
_KEY_OPT_L     = 58        # kVK_Option (Left)
_KEY_ESC       = 53        # kVK_Escape


def _request_accessibility():
    """
    Check if Accessibility is granted; if not, show the macOS prompt.
    Returns True if already trusted.
    """
    try:
        from HIServices import AXIsProcessTrustedWithOptions
        opts = NSDictionary.dictionaryWithObject_forKey_(
            True, "AXTrustedCheckOptionPrompt"
        )
        trusted = AXIsProcessTrustedWithOptions(opts)
        print(f"[VoiceType] Accessibility trusted: {trusted}", flush=True)
        return trusted
    except Exception as e:
        print(f"[VoiceType] Accessibility check error: {e}", flush=True)
        return False


class VoiceTypeApp(rumps.App):

    def __init__(self):
        super().__init__("VoiceType", quit_button="Quit VoiceType")
        self.title = "◉"

        self._audio          = AudioCapture()
        self._indicator      = None
        self._ui_q           = queue.Queue()
        self._recording      = False
        self._key_held       = False
        self._flags_monitor  = None
        self._keys_monitor   = None
        self._ax_checked     = False

        self.menu = [rumps.MenuItem("Hold  ⌥  to dictate"), None]

        self._ticker = rumps.Timer(self._tick, 1.0 / 30.0)
        self._ticker.start()

    # -- main-thread tick --

    def _tick(self, _timer):
        if self._indicator is None:
            self._indicator = RecordingIndicator()

        # Request Accessibility once on first tick (shows macOS prompt if needed)
        if not self._ax_checked:
            self._ax_checked = True
            _request_accessibility()

        # Feed real-time audio level to the indicator during recording
        if self._recording and self._indicator:
            self._indicator.set_audio_level(self._audio.rms)

        if self._flags_monitor is None:
            self._setup_monitors()

        while True:
            try:
                msg = self._ui_q.get_nowait()
            except queue.Empty:
                break

            if msg == "rec_start":
                self._indicator.show_recording()
            elif msg == "rec_stop":
                self._indicator.show_processing()
            elif msg == "paste":
                do_paste()
                self._indicator.hide()
            elif msg in ("done", "cancel"):
                self._indicator.hide()
            elif msg == "error":
                self._indicator.hide()
                rumps.notification(
                    "VoiceType", "",
                    "Could not process audio - check internet connection.",
                    sound=False,
                )

    # -- NSEvent global monitors --

    def _setup_monitors(self):
        self._flags_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            _MASK_FLAGS, self._on_flags_changed
        )
        self._keys_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            _MASK_KEYDOWN, self._on_key_down
        )
        if self._flags_monitor is None:
            rumps.notification(
                "VoiceType", "Accessibility permission needed",
                "System Settings > Privacy & Security > Accessibility > "
                "enable VoiceType, then relaunch the app.",
                sound=False,
            )

    def _on_flags_changed(self, event):
        if event.keyCode() != _KEY_OPT_L:
            return
        held = bool(event.modifierFlags() & _FLAG_OPTION)
        if held and not self._key_held:
            self._key_held = True
            self._start_recording()
        elif not held and self._key_held:
            self._key_held = False
            self._stop_recording()

    def _on_key_down(self, event):
        if event.keyCode() == _KEY_ESC and self._recording:
            self._cancel_recording()

    # -- recording lifecycle --

    def _start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._audio.start()
        self._ui_q.put("rec_start")

    def _stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        audio = self._audio.stop()
        self._ui_q.put("rec_stop")
        if audio:
            threading.Thread(target=self._process, args=(audio,), daemon=True).start()
        else:
            self._ui_q.put("done")

    def _cancel_recording(self):
        self._recording = False
        self._audio.stop()
        self._key_held = False
        self._ui_q.put("cancel")

    # -- background processing --

    def _process(self, audio):
        try:
            print(f"[VoiceType] transcribing {len(audio)} bytes...", flush=True)
            text = transcribe(audio)
            print(f"[VoiceType] transcript: '{text}'", flush=True)
            if not text:
                self._ui_q.put("done")
                return
            text = cleanup(text)
            print(f"[VoiceType] cleaned: '{text}'", flush=True)

            # Set clipboard (safe from any thread)
            set_clipboard(text)

            # Signal main thread to do the paste
            self._ui_q.put("paste")

        except Exception as exc:
            import traceback
            print(f"[VoiceType] error: {exc}", flush=True)
            traceback.print_exc()
            self._ui_q.put("error")


if __name__ == "__main__":
    # First-launch: prompt for API keys if not configured
    if not keys_configured():
        print("[VoiceType] API keys not found, showing setup dialog...", flush=True)
        if not prompt_for_keys():
            print("[VoiceType] Setup cancelled, exiting.", flush=True)
            import sys
            sys.exit(0)
    VoiceTypeApp().run()
