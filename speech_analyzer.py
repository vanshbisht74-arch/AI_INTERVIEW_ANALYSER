"""
speech_analyzer.py
-------------------
Handles microphone audio recording, speech recognition, and
speech metric analysis (WPM, pauses, speaking duration).

Runs audio capture on a background thread to avoid blocking the GUI.
"""

import time
import wave
import threading
import os
import math
from collections import deque
from typing import Optional, Dict, List, Callable

import numpy as np

from filler_word_detector import FillerWordDetector

# Optional imports – gracefully degrade if not installed
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False


class SpeechAnalyzer:
    """
    Records microphone audio in chunks, periodically transcribes via
    SpeechRecognition, and computes speech metrics in real time.
    """

    def __init__(self, settings=None, on_transcript: Optional[Callable] = None):
        self.settings = settings
        self.on_transcript = on_transcript  # callback(text: str)

        # Config
        self._sample_rate   = settings.audio_sample_rate if settings else 16000
        self._chunk_size    = settings.get("audio_chunk_size", 1024) if settings else 1024
        self._channels      = settings.get("audio_channels", 1) if settings else 1
        self._silence_rms   = settings.silence_threshold if settings else 500
        self._silence_dur   = settings.silence_duration_sec if settings else 1.5
        self._ideal_wpm_min = settings.ideal_wpm_min if settings else 120
        self._ideal_wpm_max = settings.ideal_wpm_max if settings else 160
        self._language      = settings.get("speech_language", "en-US") if settings else "en-US"
        self._recordings_dir = settings.recordings_dir if settings else "recordings"

        # State
        self._is_recording   = False
        self._audio_thread   = None
        self._recognize_thread = None
        self._lock           = threading.Lock()

        # Audio data accumulators
        self._all_frames: List[bytes] = []
        self._current_chunk_frames: List[bytes] = []

        # Metrics
        self._total_words        = 0
        self._word_timestamps: List[float] = []
        self._transcripts: List[str] = []
        self._speaking_time      = 0.0
        self._pause_count        = 0
        self._session_start      = 0.0
        self._last_speech_time   = 0.0
        self._in_pause           = False

        # Filler word detection
        self._filler_detector = FillerWordDetector()

        # Rolling RMS for live feedback
        self._rms_window: deque = deque(maxlen=20)

        # PyAudio / SpeechRecognition instances
        self._pa_instance   = None
        self._stream        = None
        self._recognizer    = None
        self._init_audio()

    # ─── Init ─────────────────────────────────────────────────────────────────

    def _init_audio(self):
        """Initialise PyAudio and SpeechRecognition."""
        if PYAUDIO_AVAILABLE:
            try:
                self._pa_instance = pyaudio.PyAudio()
            except Exception as e:
                print(f"[SpeechAnalyzer] PyAudio init error: {e}")

        if SR_AVAILABLE:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True

    # ─── Public API ───────────────────────────────────────────────────────────

    def start_recording(self, interview_id: int = 0):
        """Begin audio capture on a background thread."""
        if self._is_recording:
            return
        self.reset()
        self._session_start = time.time()
        self._last_speech_time = time.time()
        self._is_recording = True

        if PYAUDIO_AVAILABLE and self._pa_instance:
            self._audio_thread = threading.Thread(
                target=self._audio_capture_loop, daemon=True
            )
            self._audio_thread.start()

            # Periodic speech recognition on accumulated chunks
            self._recognize_thread = threading.Thread(
                target=self._recognition_loop, daemon=True
            )
            self._recognize_thread.start()
        else:
            # Mock mode
            self._audio_thread = threading.Thread(
                target=self._mock_audio_loop, daemon=True
            )
            self._audio_thread.start()

    def stop_recording(self) -> str:
        """Stop recording and save WAV. Returns the saved file path."""
        self._is_recording = False

        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=3)
        if self._recognize_thread and self._recognize_thread.is_alive():
            self._recognize_thread.join(timeout=5)

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        return self._save_wav()

    def get_live_metrics(self) -> Dict:
        """Return current metrics for real-time display."""
        elapsed = time.time() - self._session_start if self._session_start else 1
        wpm = self._compute_wpm(elapsed)
        rms = float(np.mean(self._rms_window)) if self._rms_window else 0.0
        return {
            "wpm":           round(wpm, 1),
            "word_count":    self._total_words,
            "speaking_time": round(self._speaking_time, 1),
            "pause_count":   self._pause_count,
            "rms_volume":    round(rms, 1),
            "filler_counts": self._filler_detector.get_session_totals(),
        }

    def get_summary(self) -> Dict:
        """Return complete session summary after stop."""
        elapsed = time.time() - self._session_start if self._session_start else 1
        wpm = self._compute_wpm(elapsed)

        session_filler = self._filler_detector.get_session_totals()
        return {
            "words_per_minute":  round(wpm, 1),
            "total_words":       self._total_words,
            "speaking_time_sec": round(self._speaking_time, 1),
            "pause_count":       self._pause_count,
            "transcripts":       self._transcripts,
            "full_transcript":   " ".join(self._transcripts),
            "filler_totals":     session_filler,
            "filler_word_count": session_filler.get("total", 0),
        }

    def get_speech_score(self) -> float:
        """
        Return a 0-100 speech score based on WPM and pause frequency.
        Ideal WPM 120-160; heavy pausing reduces score.
        """
        elapsed = time.time() - self._session_start if self._session_start else 1
        wpm = self._compute_wpm(elapsed)

        # WPM component
        if self._ideal_wpm_min <= wpm <= self._ideal_wpm_max:
            wpm_score = 100.0
        elif wpm < self._ideal_wpm_min:
            wpm_score = max(0, (wpm / self._ideal_wpm_min) * 100)
        else:
            excess = wpm - self._ideal_wpm_max
            wpm_score = max(0, 100 - excess * 0.5)

        # Pause penalty – many pauses suggest hesitation
        pause_penalty = min(30, self._pause_count * 2)
        score = wpm_score - pause_penalty
        return max(0.0, min(100.0, round(score, 1)))

    def get_full_transcript(self) -> str:
        return " ".join(self._transcripts)

    def reset(self):
        """Reset all state for a new session."""
        self._all_frames.clear()
        self._current_chunk_frames.clear()
        self._total_words    = 0
        self._transcripts.clear()
        self._word_timestamps.clear()
        self._speaking_time  = 0.0
        self._pause_count    = 0
        self._session_start  = 0.0
        self._last_speech_time = 0.0
        self._in_pause       = False
        self._rms_window.clear()
        self._filler_detector.reset()

    # ─── Audio capture thread ─────────────────────────────────────────────────

    def _audio_capture_loop(self):
        """Capture raw PCM audio from microphone continuously."""
        try:
            self._stream = self._pa_instance.open(
                format=pyaudio.paInt16,
                channels=self._channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk_size
            )
            while self._is_recording:
                data = self._stream.read(self._chunk_size, exception_on_overflow=False)
                with self._lock:
                    self._all_frames.append(data)
                    self._current_chunk_frames.append(data)

                # RMS for live volume meter
                rms = self._compute_rms(data)
                self._rms_window.append(rms)
                self._update_speaking_time(rms)
        except Exception as e:
            print(f"[SpeechAnalyzer] Audio capture error: {e}")

    def _mock_audio_loop(self):
        """Generate mock speech metrics when PyAudio is unavailable."""
        while self._is_recording:
            time.sleep(2)
            # Simulate speech events
            mock_words = ["The", "candidate", "demonstrates", "strong",
                          "communication", "skills", "and", "good", "presence."]
            self._total_words += len(mock_words)
            self._speaking_time += 1.8
            mock_text = " ".join(mock_words)
            self._transcripts.append(mock_text)
            if self.on_transcript:
                self.on_transcript(mock_text)

    # ─── Recognition thread ───────────────────────────────────────────────────

    def _recognition_loop(self):
        """Every ~5 seconds, recognize accumulated audio chunk."""
        while self._is_recording:
            time.sleep(5)
            self._recognize_current_chunk()

    def _recognize_current_chunk(self):
        """Transcribe the current chunk of audio frames."""
        if not SR_AVAILABLE or not self._recognizer:
            return

        with self._lock:
            if not self._current_chunk_frames:
                return
            chunk_data = b"".join(self._current_chunk_frames)
            self._current_chunk_frames.clear()

        # Write to temporary WAV in memory
        try:
            import io, wave
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)   # 16-bit
                wf.setframerate(self._sample_rate)
                wf.writeframes(chunk_data)
            wav_buffer.seek(0)

            with sr.AudioFile(wav_buffer) as source:
                audio = self._recognizer.record(source)

            text = self._recognizer.recognize_google(
                audio, language=self._language
            )
            if text:
                self._process_transcript(text)
        except sr.UnknownValueError:
            pass  # Silence or unintelligible audio
        except sr.RequestError as e:
            print(f"[SpeechAnalyzer] Recognition API error: {e}")
        except Exception as e:
            print(f"[SpeechAnalyzer] Recognition error: {e}")

    def _process_transcript(self, text: str):
        """Update metrics from a new transcript segment."""
        words = text.split()
        self._total_words += len(words)
        self._transcripts.append(text)

        now = time.time()
        for _ in words:
            self._word_timestamps.append(now)

        # Filler word analysis
        filler_result = self._filler_detector.analyze_text(text)

        if self.on_transcript:
            self.on_transcript(text)

    # ─── Metrics helpers ──────────────────────────────────────────────────────

    def _compute_rms(self, data: bytes) -> float:
        """Compute Root Mean Square amplitude of raw PCM data."""
        try:
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            return float(np.sqrt(np.mean(samples ** 2)))
        except Exception:
            return 0.0

    def _update_speaking_time(self, rms: float):
        """Track speaking vs silence to count pauses."""
        now = time.time()
        chunk_dur = self._chunk_size / self._sample_rate

        if rms > self._silence_rms:
            # Active speech
            self._speaking_time += chunk_dur
            if self._in_pause:
                self._in_pause = False
            self._last_speech_time = now
        else:
            # Silence
            silence_elapsed = now - self._last_speech_time
            if silence_elapsed > self._silence_dur and not self._in_pause:
                self._in_pause = True
                self._pause_count += 1

    def _compute_wpm(self, elapsed_sec: float) -> float:
        """Words per minute over the speaking time (not total elapsed)."""
        speaking = max(self._speaking_time, 1)
        return (self._total_words / speaking) * 60.0

    # ─── WAV file save ────────────────────────────────────────────────────────

    def _save_wav(self) -> str:
        """Write captured audio to a WAV file and return the path."""
        if not self._all_frames:
            return ""
        try:
            os.makedirs(self._recordings_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self._recordings_dir, f"interview_{ts}.wav")

            with wave.open(path, 'wb') as wf:
                wf.setnchannels(self._channels)
                wf.setsampwidth(2)
                wf.setframerate(self._sample_rate)
                wf.writeframes(b"".join(self._all_frames))

            return path
        except Exception as e:
            print(f"[SpeechAnalyzer] WAV save error: {e}")
            return ""
