"""Microphone capture using sounddevice (ships its own PortAudio — no Homebrew needed)."""

import io
import threading
import wave

import numpy as np
import sounddevice as sd

_RATE     = 16000
_CHANNELS = 1
_BLOCK    = 1024


class AudioCapture:
    def __init__(self):
        self._stream  = None
        self._frames  = []
        self._lock    = threading.Lock()
        self._active  = False
        self._rms     = 0.0        # real-time RMS level (0.0 - 1.0)

    @property
    def rms(self):
        """Current audio RMS level, normalized 0.0-1.0. Thread-safe read."""
        return self._rms

    def start(self):
        self._frames = []
        self._rms    = 0.0
        self._active = True
        self._stream = sd.InputStream(
            samplerate=_RATE,
            channels=_CHANNELS,
            dtype="int16",
            blocksize=_BLOCK,
            callback=self._cb,
        )
        self._stream.start()

    def _cb(self, indata, _frames, _time, _status):
        if self._active:
            with self._lock:
                self._frames.append(indata.copy())
            # Compute RMS and normalize to 0.0-1.0 range
            # int16 max is 32768; typical speech RMS is ~1000-5000
            rms_raw = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
            self._rms = min(rms_raw / 6000.0, 1.0)

    def stop(self):
        """Stop recording and return WAV bytes, or None if nothing was captured."""
        self._active = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = self._frames[:]

        if not frames:
            return None

        pcm = np.concatenate(frames, axis=0)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(_CHANNELS)
            wf.setsampwidth(2)          # int16 = 2 bytes
            wf.setframerate(_RATE)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()
