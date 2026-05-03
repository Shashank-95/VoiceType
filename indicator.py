"""
Premium floating pill indicator with audio-reactive waveform.

Recording state:  pulsing red dot + bars that respond to actual voice input
Processing state: smooth cascading dots animation

All public methods must be called on the main thread.
"""

import math
import time
import objc

from AppKit import (
    NSWindow, NSView, NSColor, NSBezierPath, NSFont, NSMutableParagraphStyle,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSScreen, NSApplication,
    NSMutableDictionary,
    NSForegroundColorAttributeName,
    NSFontAttributeName,
    NSParagraphStyleAttributeName,
    NSAttributedString,
    NSShadow,
)
from Foundation import NSObject, NSTimer, NSMakeRect, NSMakePoint, NSMakeSize
import Quartz  # noqa: F401

# ── constants ──────────────────────────────────────────────────────────────
NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
_WINDOW_LEVEL = 25

# ── premium colour palette ─────────────────────────────────────────────────
_BG_R, _BG_G, _BG_B, _BG_A = 0.08, 0.08, 0.10, 0.94
_BORDER_R, _BORDER_G, _BORDER_B, _BORDER_A = 1.0, 1.0, 1.0, 0.06
_BAR_R, _BAR_G, _BAR_B = 1.0, 1.0, 1.0
_REC_DOT_R, _REC_DOT_G, _REC_DOT_B = 1.0, 0.22, 0.22
_DOT_R, _DOT_G, _DOT_B = 1.0, 1.0, 1.0

# Number of waveform bars
_NUM_BARS = 7


# ── NSTimer bridge ─────────────────────────────────────────────────────────
class _TimerTarget(NSObject):
    def initWithView_(self, view):
        self = objc.super(_TimerTarget, self).init()
        if self is None:
            return None
        self._view = view
        return self

    def tick_(self, _timer):
        self._view.setNeedsDisplay_(True)


# ── custom drawing view ────────────────────────────────────────────────────
class _PillContentView(NSView):
    RECORDING  = "recording"
    PROCESSING = "processing"

    # Per-bar smoothed levels (for silky animation)
    _bar_levels = [0.0] * _NUM_BARS
    # Phase offsets so each bar responds slightly differently
    _BAR_OFFSETS = [0.0, 0.12, 0.06, 0.15, 0.09, 0.13, 0.04]

    def initWithFrame_(self, frame):
        self = objc.super(_PillContentView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._state        = None
        self._t0           = 0.0
        self._anim_timer   = None
        self._timer_target = None
        self._audio_level  = 0.0
        self._bar_levels   = [0.0] * _NUM_BARS
        return self

    @objc.python_method
    def set_state(self, state):
        self._state = state
        self._t0    = time.time()
        if state is not None:
            self._start_timer()
        else:
            self._stop_timer()
        # Reset bars on state change
        self._bar_levels = [0.0] * _NUM_BARS
        self._audio_level = 0.0
        self.setNeedsDisplay_(True)

    @objc.python_method
    def set_audio_level(self, level):
        """Set current audio RMS level (0.0-1.0). Called from main thread."""
        self._audio_level = level

    @objc.python_method
    def _start_timer(self):
        if self._anim_timer is not None:
            return
        self._timer_target = _TimerTarget.alloc().initWithView_(self)
        self._anim_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0 / 60.0,   # 60fps for smoother animation
            self._timer_target,
            "tick:",
            None,
            True,
        )

    @objc.python_method
    def _stop_timer(self):
        if self._anim_timer is not None:
            self._anim_timer.invalidate()
            self._anim_timer   = None
            self._timer_target = None

    # ── NSView override ────────────────────────────────────────────────────

    def drawRect_(self, rect):
        w = rect.size.width
        h = rect.size.height

        # ── Pill background with subtle gradient feel ──
        bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, w, h), h / 2.0, h / 2.0
        )

        # Dark background
        NSColor.colorWithRed_green_blue_alpha_(
            _BG_R, _BG_G, _BG_B, _BG_A
        ).setFill()
        bg.fill()

        # Inner subtle highlight at top edge (premium glass effect)
        highlight = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(1, h * 0.5, w - 2, h * 0.48), (h * 0.48) / 2.0, (h * 0.48) / 2.0
        )
        NSColor.colorWithRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.03).setFill()
        highlight.fill()

        # Subtle outer border
        NSColor.colorWithRed_green_blue_alpha_(
            _BORDER_R, _BORDER_G, _BORDER_B, _BORDER_A
        ).setStroke()
        bg.setLineWidth_(0.5)
        bg.stroke()

        state = getattr(self, "_state", None)
        if state == self.RECORDING:
            self._draw_recording(w, h)
        elif state == self.PROCESSING:
            self._draw_processing(w, h)

    # ── Recording: red dot + audio-reactive bars ───────────────────────────

    @objc.python_method
    def _draw_recording(self, w, h):
        t  = time.time() - self._t0
        cy = h / 2.0
        level = self._audio_level

        # ── Smooth red recording dot with glow ──
        pulse = 0.7 + 0.3 * (0.5 + 0.5 * math.sin(t * 2.5))
        dr = 5.0
        dx = 24.0

        # Glow behind dot
        glow_r = dr * 2.5
        NSColor.colorWithRed_green_blue_alpha_(
            _REC_DOT_R, _REC_DOT_G, _REC_DOT_B, 0.15 * pulse
        ).setFill()
        NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(dx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)
        ).fill()

        # Dot itself
        NSColor.colorWithRed_green_blue_alpha_(
            _REC_DOT_R, _REC_DOT_G, _REC_DOT_B, pulse
        ).setFill()
        NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(dx - dr, cy - dr, dr * 2, dr * 2)
        ).fill()

        # ── Thin separator line ──
        sep_x = dx + dr + 12.0
        NSColor.colorWithRed_green_blue_alpha_(1.0, 1.0, 1.0, 0.10).setFill()
        NSBezierPath.fillRect_(NSMakeRect(sep_x, h * 0.25, 0.5, h * 0.50))

        # ── Audio-reactive waveform bars ──
        bar_w    = 3.0
        bar_gap  = 4.5
        num_bars = _NUM_BARS
        total_w  = num_bars * bar_w + (num_bars - 1) * bar_gap
        start_x  = sep_x + 12.0
        min_h    = 3.0
        max_h    = h * 0.65

        for i in range(num_bars):
            # Target height based on audio level + per-bar variation
            offset = self._BAR_OFFSETS[i % len(self._BAR_OFFSETS)]
            # Create slight variation per bar from the audio level
            variation = 0.6 + 0.4 * math.sin(t * 3.0 + i * 1.2 + offset * 10.0)
            target = level * variation

            # Smooth interpolation (bars rise fast, fall slowly)
            current = self._bar_levels[i]
            if target > current:
                self._bar_levels[i] = current + (target - current) * 0.4   # fast rise
            else:
                self._bar_levels[i] = current + (target - current) * 0.12  # slow fall

            smoothed = self._bar_levels[i]

            # Minimum idle animation when quiet
            idle = 0.08 + 0.06 * math.sin(t * 1.5 + i * 0.9)
            final_level = max(smoothed, idle)

            bh = min_h + final_level * (max_h - min_h)
            bx = start_x + i * (bar_w + bar_gap)
            by = cy - bh / 2.0

            # Bar opacity varies with height for depth
            alpha = 0.4 + 0.6 * final_level
            NSColor.colorWithRed_green_blue_alpha_(
                _BAR_R, _BAR_G, _BAR_B, max(0.35, alpha)
            ).setFill()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(bx, by, bar_w, bh),
                bar_w / 2.0, bar_w / 2.0,
            ).fill()

    # ── Processing: cascading dots ─────────────────────────────────────────

    @objc.python_method
    def _draw_processing(self, w, h):
        t  = time.time() - self._t0
        cy = h / 2.0

        num_dots = 3
        dr       = 4.0
        gap      = 16.0
        tw       = num_dots * dr * 2 + (num_dots - 1) * gap
        start    = (w - tw) / 2.0 + dr

        for i in range(num_dots):
            # Smooth cascading wave
            phase = t * 2.2 - i * 0.5
            wave = 0.5 + 0.5 * math.sin(phase)

            # Dots scale and fade
            alpha = 0.15 + 0.85 * wave
            scale = 0.7 + 0.3 * wave
            r = dr * scale

            cx = start + i * (dr * 2 + gap)

            # Subtle glow
            if wave > 0.6:
                glow_r = r * 2.0
                NSColor.colorWithRed_green_blue_alpha_(
                    _DOT_R, _DOT_G, _DOT_B, 0.06 * wave
                ).setFill()
                NSBezierPath.bezierPathWithOvalInRect_(
                    NSMakeRect(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)
                ).fill()

            NSColor.colorWithRed_green_blue_alpha_(
                _DOT_R, _DOT_G, _DOT_B, alpha
            ).setFill()
            NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(cx - r, cy - r, r * 2, r * 2)
            ).fill()


# ── public interface ───────────────────────────────────────────────────────
class RecordingIndicator:
    """
    Floating dark pill indicator.
    Must be created and used on the main AppKit thread.
    """

    PILL_W = 180
    PILL_H = 44

    def __init__(self):
        self._win  = None
        self._view = None
        self._build()

    def _build(self):
        screen = NSScreen.mainScreen()
        if screen is None:
            print("[VoiceType] WARNING: no main screen", flush=True)
            return
        sf = screen.frame()
        vf = screen.visibleFrame()

        # Centre horizontally, above Dock
        x = (sf.size.width - self.PILL_W) / 2.0
        y = vf.origin.y + 28.0

        self._win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, self.PILL_W, self.PILL_H),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        self._win.setLevel_(_WINDOW_LEVEL)
        self._win.setOpaque_(False)
        self._win.setBackgroundColor_(NSColor.clearColor())
        self._win.setHasShadow_(True)
        self._win.setIgnoresMouseEvents_(True)
        self._win.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces)
        self._win.setHidesOnDeactivate_(False)

        self._view = _PillContentView.alloc().initWithFrame_(
            NSMakeRect(0, 0, self.PILL_W, self.PILL_H)
        )
        self._win.setContentView_(self._view)

        print("[VoiceType] indicator ready at ({:.0f}, {:.0f})".format(x, y), flush=True)

    def show_recording(self):
        if self._win is None:
            return
        self._view.set_state(_PillContentView.RECORDING)
        self._win.orderFrontRegardless()
        self._win.setAlphaValue_(1.0)

    def show_processing(self):
        if self._win is None:
            return
        self._view.set_state(_PillContentView.PROCESSING)
        self._win.orderFrontRegardless()
        self._win.setAlphaValue_(1.0)

    def set_audio_level(self, level):
        """Feed real-time audio level to the view."""
        if self._view is not None:
            self._view.set_audio_level(level)

    def hide(self):
        if self._win is None:
            return
        self._view.set_state(None)
        self._win.setAlphaValue_(0.0)
        self._win.orderOut_(None)
