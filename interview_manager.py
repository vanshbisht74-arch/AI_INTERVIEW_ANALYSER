"""
interview_manager.py
---------------------
Orchestrates a full interview session: webcam capture, audio recording,
real-time analysis, score computation, and database persistence.

Runs the video-capture loop on the calling thread (via update_frame()),
which must be called periodically from the GUI's after() loop.
"""

import time
import threading
import os
from datetime import datetime
from typing import Optional, Callable, Dict, Any

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from settings_manager    import SettingsManager
from database_manager    import DatabaseManager
from eye_contact_analyzer import EyeContactAnalyzer
from speech_analyzer      import SpeechAnalyzer
from confidence_calculator import ConfidenceCalculator
from report_generator     import ReportGenerator


class InterviewSession:
    """Value object holding all data for one interview attempt."""

    def __init__(self, candidate_id: int, candidate_name: str, interview_id: int):
        self.candidate_id   = candidate_id
        self.candidate_name = candidate_name
        self.interview_id   = interview_id
        self.start_time     = time.time()
        self.end_time: Optional[float] = None
        self.scores: Dict   = {}
        self.metrics: Dict  = {}
        self.strengths: list  = []
        self.improvements: list = []
        self.report_path    = ""
        self.recording_path = ""

    @property
    def duration_sec(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time


class InterviewManager:
    """
    High-level controller for an interview session.

    Usage (GUI integration):
        mgr = InterviewManager(settings, db, on_frame_cb, on_metric_cb)
        mgr.start_session(candidate_name)
        # GUI calls mgr.get_current_frame() every 33 ms
        mgr.stop_session()
        report_path = mgr.generate_report()
    """

    def __init__(
        self,
        settings: SettingsManager,
        db: DatabaseManager,
        on_frame: Optional[Callable]   = None,   # callback(annotated_frame: np.ndarray)
        on_metrics: Optional[Callable] = None,   # callback(metrics_dict)
        on_transcript: Optional[Callable] = None # callback(text: str)
    ):
        self.settings  = settings
        self.db        = db
        self.on_frame  = on_frame
        self.on_metrics = on_metrics

        # Sub-analysers
        self.eye_analyzer   = EyeContactAnalyzer(settings)
        self.speech_analyzer = SpeechAnalyzer(settings, on_transcript=on_transcript)
        self.confidence_calc = ConfidenceCalculator(settings)
        self.report_gen      = ReportGenerator(settings)

        # Session state
        self.session: Optional[InterviewSession] = None
        self._is_running = False
        self._cap        = None   # cv2.VideoCapture
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None

        # Live metric snapshot (thread-safe)
        self._live_metrics: Dict = {}
        self._metric_lock  = threading.Lock()

    # ─── Session lifecycle ────────────────────────────────────────────────────

    def start_session(self, candidate_name: str) -> InterviewSession:
        """
        Start a new interview session for the given candidate.
        Opens webcam and begins audio capture.
        """
        if self._is_running:
            raise RuntimeError("A session is already running.")

        # Resolve or create candidate
        candidate_id = self.db.get_or_create_candidate(candidate_name)

        # Create DB interview record
        interview_id = self.db.create_interview(candidate_id)

        # Reset analysers
        self.eye_analyzer.reset()
        self.speech_analyzer.reset()

        # Build session object
        self.session = InterviewSession(candidate_id, candidate_name, interview_id)
        self._is_running = True

        # Open webcam
        self._open_camera()

        # Start audio
        self.speech_analyzer.start_recording(interview_id)

        return self.session

    def stop_session(self) -> Optional[InterviewSession]:
        """Stop the session, compute scores, and persist to DB."""
        if not self._is_running or not self.session:
            return None

        self._is_running = False
        self.session.end_time = time.time()

        # Stop audio and get recording path
        wav_path = self.speech_analyzer.stop_recording()
        self.session.recording_path = wav_path

        # Release camera
        self._close_camera()

        # Gather metrics
        eye_summary    = self.eye_analyzer.get_summary()
        speech_summary = self.speech_analyzer.get_summary()

        raw_metrics = {**eye_summary, **speech_summary}
        self.session.metrics = raw_metrics

        # Compute scores
        scores = self.confidence_calc.calculate(
            eye_contact_pct    = eye_summary.get("eye_contact_pct",  0),
            words_per_minute   = speech_summary.get("words_per_minute", 0),
            filler_word_count  = speech_summary.get("filler_word_count", 0),
            head_stability     = eye_summary.get("head_stability", 0.85),
            smile_percentage   = eye_summary.get("smile_percentage", 0),
            speaking_time_sec  = speech_summary.get("speaking_time_sec", 0),
            total_session_sec  = self.session.duration_sec,
            pause_count        = speech_summary.get("pause_count", 0),
        )
        self.session.scores = scores

        # Generate strengths / improvements
        feedback = self.confidence_calc.generate_strengths_and_improvements(
            scores, {**raw_metrics, **scores}
        )
        self.session.strengths    = feedback["strengths"]
        self.session.improvements = feedback["improvements"]

        # Persist scores to DB
        self.db.save_scores(self.session.interview_id, {
            **scores,
            "eye_contact_pct":   eye_summary.get("eye_contact_pct", 0),
            "words_per_minute":  speech_summary.get("words_per_minute", 0),
            "filler_word_count": speech_summary.get("filler_word_count", 0),
            "speaking_time_sec": speech_summary.get("speaking_time_sec", 0),
            "pause_count":       speech_summary.get("pause_count", 0),
            "smile_percentage":  eye_summary.get("smile_percentage", 0),
            "head_stability":    eye_summary.get("head_stability", 0),
            "raw_metrics":       raw_metrics,
        })

        # Update interview duration
        self.db.update_interview_duration(
            self.session.interview_id, self.session.duration_sec
        )

        return self.session

    def generate_report(self) -> str:
        """Generate PDF report for the completed session. Returns file path."""
        if not self.session:
            return ""
        path = self.report_gen.generate(self.session)
        self.session.report_path = path

        self.db.save_report(
            self.session.interview_id,
            path,
            self.session.strengths,
            self.session.improvements,
        )
        return path

    # ─── Frame update (called by GUI every ~33 ms) ────────────────────────────

    def update_frame(self):
        """
        Grab one frame from the webcam, run eye analysis, update live metrics.
        Must be called from the GUI thread (or via after()).
        """
        if not self._is_running or self._cap is None:
            return

        if CV2_AVAILABLE:
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return
            # Mirror for natural webcam feel
            frame = cv2.flip(frame, 1)
        else:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Eye / facial analysis
        eye_result = self.eye_analyzer.process_frame(frame)
        annotated  = eye_result.get("annotated_frame", frame)

        with self._frame_lock:
            self._latest_frame = annotated

        # Merge live metrics
        speech_live = self.speech_analyzer.get_live_metrics()
        live = {
            "eye_contact":  eye_result.get("eye_contact", False),
            "gaze_score":   eye_result.get("gaze_score",  0.0),
            "blinks":       eye_result.get("blinks",      0),
            "head_stable":  eye_result.get("head_stable", True),
            "smile":        eye_result.get("smile",       False),
            **speech_live,
            "elapsed_sec":  (time.time() - self.session.start_time)
                             if self.session else 0,
        }

        with self._metric_lock:
            self._live_metrics = live

        if self.on_metrics:
            self.on_metrics(live)
        if self.on_frame:
            self.on_frame(annotated)

    # ─── Getters ──────────────────────────────────────────────────────────────

    def get_current_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return self._latest_frame

    def get_live_metrics(self) -> Dict:
        with self._metric_lock:
            return dict(self._live_metrics)

    def is_running(self) -> bool:
        return self._is_running

    # ─── Camera helpers ───────────────────────────────────────────────────────

    def _open_camera(self):
        if not CV2_AVAILABLE:
            return
        idx = self.settings.camera_index
        self._cap = cv2.VideoCapture(idx)
        if not self._cap.isOpened():
            # Try default camera
            self._cap = cv2.VideoCapture(0)
        if self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.settings.frame_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.frame_height)
            self._cap.set(cv2.CAP_PROP_FPS,          self.settings.get("camera_fps", 30))

    def _close_camera(self):
        if self._cap:
            self._cap.release()
            self._cap = None
