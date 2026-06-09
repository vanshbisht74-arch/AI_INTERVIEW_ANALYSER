"""
replay_manager.py
-----------------
Interview Replay System.
Plays back a recorded interview WAV alongside its stored metrics,
providing a frame-by-frame timeline scrubber and metric overlay.

Works without the original video (audio-only replay with metric animation),
or with a saved video file when available.
"""

import os
import time
import threading
import json
from typing import Optional, Dict, List, Callable

try:
    import wave
    WAVE_AVAILABLE = True
except ImportError:
    WAVE_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


class ReplayEvent:
    """A single timestamped event in the replay timeline."""

    def __init__(self, timestamp: float, event_type: str, data: Dict):
        self.timestamp  = timestamp   # seconds from session start
        self.event_type = event_type  # 'metric' | 'transcript' | 'filler'
        self.data       = data


class ReplayManager:
    """
    Loads stored session data and provides a playback interface.

    The caller provides:
      on_tick(elapsed_sec, metrics_snapshot) — called ~10x/sec during playback
      on_transcript(text)                    — called when a transcript segment fires
      on_complete()                          — called when playback ends
    """

    def __init__(
        self,
        on_tick:       Optional[Callable] = None,
        on_transcript: Optional[Callable] = None,
        on_complete:   Optional[Callable] = None,
    ):
        self.on_tick       = on_tick
        self.on_transcript = on_transcript
        self.on_complete   = on_complete

        # Playback state
        self._events:       List[ReplayEvent] = []
        self._duration_sec: float = 0.0
        self._scores:       Dict  = {}
        self._metrics:      Dict  = {}
        self._wav_path:     str   = ""

        self._is_playing    = False
        self._is_paused     = False
        self._play_start:   float = 0.0
        self._pause_offset: float = 0.0

        self._thread: Optional[threading.Thread] = None
        self._pa:     Optional[object] = None
        self._stream: Optional[object] = None

    # ─── Load ─────────────────────────────────────────────────────────────────

    def load_session(
        self,
        scores:      Dict,
        metrics:     Dict,
        transcripts: List[str],
        duration_sec: float,
        wav_path:    str = "",
    ):
        """
        Populate the replay timeline from stored session data.
        Synthetic events are generated from aggregate metrics.
        """
        self._scores      = scores
        self._metrics     = metrics
        self._duration_sec = max(duration_sec, 1.0)
        self._wav_path    = wav_path
        self._events      = []

        # Build synthetic metric events spread across the session
        self._build_metric_events()

        # Build transcript events (equally spaced)
        if transcripts:
            interval = self._duration_sec / len(transcripts)
            for i, text in enumerate(transcripts):
                self._events.append(ReplayEvent(
                    timestamp  = i * interval,
                    event_type = "transcript",
                    data       = {"text": text}
                ))

        # Sort by timestamp
        self._events.sort(key=lambda e: e.timestamp)

    def _build_metric_events(self):
        """
        Generate ~1-per-second metric snapshots that animate smoothly
        from 0 toward the final recorded values.
        """
        final_eye   = self._scores.get("eye_contact_score",   0)
        final_conf  = self._scores.get("confidence_score",    0)
        final_speech = self._scores.get("speech_score",       0)
        final_overall = self._scores.get("overall_score",     0)
        final_wpm   = self._metrics.get("words_per_minute",   0)
        final_eye_pct = self._metrics.get("eye_contact_pct",  0)
        fillers     = self._metrics.get("filler_word_count",  0)
        pauses      = self._metrics.get("pause_count",        0)

        steps = max(10, int(self._duration_sec))
        for i in range(steps + 1):
            t = (i / steps) * self._duration_sec
            # Ramp: starts at ~40% of final, reaches 100% at end
            pct = 0.4 + 0.6 * (i / steps)
            self._events.append(ReplayEvent(
                timestamp  = t,
                event_type = "metric",
                data       = {
                    "eye_contact_score":   round(final_eye   * pct, 1),
                    "confidence_score":    round(final_conf  * pct, 1),
                    "speech_score":        round(final_speech * pct, 1),
                    "overall_score":       round(final_overall * pct, 1),
                    "words_per_minute":    round(final_wpm   * pct, 1),
                    "eye_contact_pct":     round(final_eye_pct * pct, 1),
                    "filler_word_count":   int(fillers * pct),
                    "pause_count":         int(pauses  * pct),
                    "elapsed_sec":         t,
                }
            ))

    # ─── Playback control ─────────────────────────────────────────────────────

    def play(self, start_offset: float = 0.0):
        """Start or resume playback from start_offset seconds."""
        if self._is_playing:
            return
        self._is_playing    = True
        self._is_paused     = False
        self._pause_offset  = start_offset
        self._play_start    = time.time() - start_offset

        self._thread = threading.Thread(
            target=self._playback_loop, daemon=True
        )
        self._thread.start()

        if self._wav_path and os.path.exists(self._wav_path) and PYAUDIO_AVAILABLE:
            threading.Thread(
                target=self._play_audio,
                args=(start_offset,),
                daemon=True
            ).start()

    def pause(self):
        """Pause playback, recording current position."""
        if not self._is_playing or self._is_paused:
            return
        self._pause_offset = time.time() - self._play_start
        self._is_paused    = True
        self._is_playing   = False
        self._stop_audio()

    def seek(self, offset_sec: float):
        """Jump to a specific position in the timeline."""
        was_playing = self._is_playing
        self._is_playing = False
        time.sleep(0.05)  # let loop exit
        if was_playing:
            self.play(start_offset=offset_sec)
        else:
            self._pause_offset = offset_sec

    def stop(self):
        """Stop playback completely."""
        self._is_playing = False
        self._is_paused  = False
        self._stop_audio()

    @property
    def current_position(self) -> float:
        """Current playback position in seconds."""
        if self._is_playing:
            return time.time() - self._play_start
        return self._pause_offset

    @property
    def duration(self) -> float:
        return self._duration_sec

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    # ─── Playback loop ────────────────────────────────────────────────────────

    def _playback_loop(self):
        """Main playback thread — fires events at correct timestamps."""
        next_event_idx = self._find_next_event(self._pause_offset)

        while self._is_playing:
            elapsed = time.time() - self._play_start

            # End of session
            if elapsed >= self._duration_sec:
                self._is_playing = False
                if self.on_complete:
                    self.on_complete()
                return

            # Fire due events
            while (next_event_idx < len(self._events) and
                   self._events[next_event_idx].timestamp <= elapsed):
                evt = self._events[next_event_idx]
                self._dispatch_event(evt)
                next_event_idx += 1

            # Tick callback
            if self.on_tick:
                # Find latest metric snapshot
                snapshot = self._latest_metric_snapshot(elapsed)
                self.on_tick(elapsed, snapshot)

            time.sleep(0.1)   # 10 Hz tick

    def _dispatch_event(self, evt: ReplayEvent):
        if evt.event_type == "transcript" and self.on_transcript:
            self.on_transcript(evt.data.get("text", ""))

    def _find_next_event(self, offset: float) -> int:
        for i, evt in enumerate(self._events):
            if evt.timestamp >= offset:
                return i
        return len(self._events)

    def _latest_metric_snapshot(self, elapsed: float) -> Dict:
        """Return the most recent metric event at or before elapsed."""
        result = {}
        for evt in self._events:
            if evt.event_type == "metric" and evt.timestamp <= elapsed:
                result = evt.data
            elif evt.timestamp > elapsed:
                break
        return result

    # ─── Audio playback ───────────────────────────────────────────────────────

    def _play_audio(self, start_offset: float):
        """Play WAV file from start_offset."""
        if not PYAUDIO_AVAILABLE:
            return
        try:
            self._pa = pyaudio.PyAudio()
            with wave.open(self._wav_path, 'rb') as wf:
                sample_rate   = wf.getframerate()
                sample_width  = wf.getsampwidth()
                channels      = wf.getnchannels()

                # Seek to offset
                frame_offset = int(start_offset * sample_rate)
                wf.setpos(min(frame_offset, wf.getnframes()))

                chunk = 1024
                fmt   = self._pa.get_format_from_width(sample_width)
                self._stream = self._pa.open(
                    format=fmt,
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                )
                while self._is_playing:
                    data = wf.readframes(chunk)
                    if not data:
                        break
                    self._stream.write(data)
        except Exception as e:
            print(f"[ReplayManager] Audio playback error: {e}")
        finally:
            self._stop_audio()

    def _stop_audio(self):
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
            if self._pa:
                self._pa.terminate()
                self._pa = None
        except Exception:
            pass
