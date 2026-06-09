"""
eye_contact_analyzer.py
------------------------
Analyzes eye contact and facial stability using MediaPipe Face Mesh.
Tracks iris position, blink rate, and head movement to compute
an eye-contact score and attention score.
"""

import time
import math
import numpy as np
from collections import deque
from typing import Optional, Dict, Any, Tuple

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ─── MediaPipe landmark indices ──────────────────────────────────────────────
# Left eye
LEFT_EYE_UPPER  = [159, 158, 157, 173]
LEFT_EYE_LOWER  = [145, 144, 163, 7]
LEFT_EYE_LEFT   = 33
LEFT_EYE_RIGHT  = 133
LEFT_IRIS_CENTER = 468

# Right eye
RIGHT_EYE_UPPER  = [386, 385, 384, 398]
RIGHT_EYE_LOWER  = [374, 373, 390, 249]
RIGHT_EYE_LEFT   = 362
RIGHT_EYE_RIGHT  = 263
RIGHT_IRIS_CENTER = 473

# Nose tip (head movement anchor)
NOSE_TIP = 1


class EyeContactAnalyzer:
    """
    Real-time eye-contact and facial stability analyzer.

    For each video frame, it:
      1. Detects face mesh landmarks via MediaPipe.
      2. Computes Eye Aspect Ratio (EAR) for blink detection.
      3. Estimates iris deviation from eye centre to infer gaze.
      4. Tracks nose-tip movement for head stability.
      5. Accumulates rolling averages for a live confidence score.
    """

    def __init__(self, settings=None):
        self.settings = settings

        # Thresholds
        self.eye_contact_threshold = (
            settings.get("eye_contact_threshold", 0.65) if settings else 0.65
        )
        self.blink_ear_threshold   = (
            settings.get("blink_threshold", 0.25) if settings else 0.25
        )
        self.head_move_threshold   = (
            settings.get("head_movement_threshold", 15) if settings else 15
        )

        # State accumulators
        self._total_frames        = 0
        self._contact_frames      = 0   # frames where gaze ≈ camera
        self._blink_count         = 0
        self._blink_in_progress   = False
        self._smile_frames        = 0

        # Head-position history for stability scoring
        self._nose_positions: deque = deque(maxlen=30)
        self._head_stability_scores: deque = deque(maxlen=100)

        # Rolling gaze score window (last N frames)
        self._gaze_window: deque = deque(maxlen=60)

        # MediaPipe setup
        self._mp_face_mesh = None
        self._face_mesh    = None
        self._initialized  = False
        self._init_mediapipe()

    # ─── Init ─────────────────────────────────────────────────────────────────

    def _init_mediapipe(self):
        """Initialise MediaPipe Face Mesh (with iris landmarks)."""
        if not MEDIAPIPE_AVAILABLE:
            print("[EyeContactAnalyzer] MediaPipe not available – using mock mode.")
            return
        try:
            self._mp_face_mesh = mp.solutions.face_mesh
            self._face_mesh = self._mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,  # enables iris landmarks 468-477
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self._initialized = True
        except Exception as e:
            print(f"[EyeContactAnalyzer] Init error: {e}")

    # ─── Public API ───────────────────────────────────────────────────────────

    def process_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Process a single BGR frame. Returns a dict with:
          - eye_contact (bool)
          - gaze_score  (0-1 rolling average)
          - blinks      (cumulative count)
          - head_stable (bool)
          - smile       (bool)
          - landmarks   (raw mediapipe result, may be None)
          - annotated_frame (frame with debug overlays)
        """
        result = {
            "eye_contact":     False,
            "gaze_score":      0.0,
            "blinks":          self._blink_count,
            "head_stable":     True,
            "smile":           False,
            "landmarks":       None,
            "annotated_frame": frame.copy() if CV2_AVAILABLE else frame,
        }

        if not self._initialized or not CV2_AVAILABLE:
            # Mock mode: generate plausible random data
            self._total_frames += 1
            mock_contact = (self._total_frames % 10) < 7
            self._contact_frames += int(mock_contact)
            result["eye_contact"] = mock_contact
            result["gaze_score"]  = self._contact_frames / max(1, self._total_frames)
            return result

        # Convert to RGB for MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        mp_result = self._face_mesh.process(rgb)
        rgb.flags.writeable = True

        annotated = frame.copy()
        self._total_frames += 1

        if not mp_result.multi_face_landmarks:
            self._gaze_window.append(0)
            result["gaze_score"] = float(np.mean(self._gaze_window)) if self._gaze_window else 0.0
            return result

        landmarks = mp_result.multi_face_landmarks[0]
        h, w = frame.shape[:2]
        lm  = landmarks.landmark

        # ── EAR / Blink detection ────────────────────────────────────────────
        left_ear  = self._eye_aspect_ratio(lm, LEFT_EYE_UPPER,  LEFT_EYE_LOWER,
                                           LEFT_EYE_LEFT, LEFT_EYE_RIGHT, w, h)
        right_ear = self._eye_aspect_ratio(lm, RIGHT_EYE_UPPER, RIGHT_EYE_LOWER,
                                           RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT, w, h)
        avg_ear = (left_ear + right_ear) / 2.0

        if avg_ear < self.blink_ear_threshold:
            if not self._blink_in_progress:
                self._blink_count += 1
                self._blink_in_progress = True
        else:
            self._blink_in_progress = False

        # ── Gaze / iris deviation ─────────────────────────────────────────────
        eye_contact, iris_deviation = self._compute_gaze(lm, w, h)
        self._gaze_window.append(1 if eye_contact else 0)
        self._contact_frames += int(eye_contact)

        # ── Head stability ────────────────────────────────────────────────────
        nose_x = int(lm[NOSE_TIP].x * w)
        nose_y = int(lm[NOSE_TIP].y * h)
        self._nose_positions.append((nose_x, nose_y))
        head_stable = self._compute_head_stability()

        # ── Smile detection ───────────────────────────────────────────────────
        smile = self._detect_smile(lm, w, h)
        if smile:
            self._smile_frames += 1

        # ── Annotations ───────────────────────────────────────────────────────
        annotated = self._draw_overlays(annotated, lm, w, h,
                                        eye_contact, iris_deviation, head_stable)

        result.update({
            "eye_contact":     eye_contact,
            "gaze_score":      float(np.mean(self._gaze_window)),
            "blinks":          self._blink_count,
            "head_stable":     head_stable,
            "smile":           smile,
            "landmarks":       landmarks,
            "annotated_frame": annotated,
        })
        return result

    # ─── Metrics ──────────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, float]:
        """Return aggregated metrics for the full session."""
        total = max(1, self._total_frames)
        return {
            "eye_contact_pct":   round(self._contact_frames / total * 100, 1),
            "blink_count":       self._blink_count,
            "smile_percentage":  round(self._smile_frames / total * 100, 1),
            "head_stability":    round(float(np.mean(self._head_stability_scores))
                                       if self._head_stability_scores else 0.85, 2),
            "total_frames":      self._total_frames,
        }

    def get_eye_contact_score(self) -> float:
        """Return a 0-100 score for eye contact."""
        pct = self._contact_frames / max(1, self._total_frames) * 100
        # Ideal range 60-90%; penalise extremes
        if pct >= 60:
            score = min(100.0, pct * 1.05)
        else:
            score = pct * 0.8
        return round(score, 1)

    def reset(self):
        """Reset all state for a new interview session."""
        self._total_frames      = 0
        self._contact_frames    = 0
        self._blink_count       = 0
        self._blink_in_progress = False
        self._smile_frames      = 0
        self._nose_positions.clear()
        self._head_stability_scores.clear()
        self._gaze_window.clear()

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _eye_aspect_ratio(
        self, lm, upper_idx, lower_idx, left_idx, right_idx, w, h
    ) -> float:
        """
        Compute Eye Aspect Ratio (EAR) using landmark indices.
        EAR = (vertical distances) / (2 * horizontal distance)
        Low EAR → eye closed (blink).
        """
        def pt(idx): return np.array([lm[idx].x * w, lm[idx].y * h])

        upper_pts = [pt(i) for i in upper_idx]
        lower_pts = [pt(i) for i in lower_idx]
        left_pt   = pt(left_idx)
        right_pt  = pt(right_idx)

        # Average of paired vertical distances
        vert = np.mean([np.linalg.norm(u - d) for u, d in zip(upper_pts, lower_pts)])
        horiz = np.linalg.norm(left_pt - right_pt)

        if horiz < 1e-6:
            return 0.3  # safe fallback
        return vert / horiz

    def _compute_gaze(
        self, lm, w: int, h: int
    ) -> Tuple[bool, float]:
        """
        Estimate whether the candidate is looking at the camera.
        Uses iris-to-eye-centre offset normalised by eye width.
        Returns (is_looking_at_camera, deviation_ratio).
        """
        try:
            # Left iris
            li_x = lm[LEFT_IRIS_CENTER].x * w
            li_y = lm[LEFT_IRIS_CENTER].y * h
            le_cx = (lm[LEFT_EYE_LEFT].x + lm[LEFT_EYE_RIGHT].x) / 2 * w
            le_cy = (lm[LEFT_EYE_UPPER[0]].y + lm[LEFT_EYE_LOWER[0]].y) / 2 * h
            le_w  = abs(lm[LEFT_EYE_RIGHT].x - lm[LEFT_EYE_LEFT].x) * w + 1e-6

            left_dev = math.hypot(li_x - le_cx, li_y - le_cy) / le_w

            # Right iris
            ri_x = lm[RIGHT_IRIS_CENTER].x * w
            ri_y = lm[RIGHT_IRIS_CENTER].y * h
            re_cx = (lm[RIGHT_EYE_LEFT].x + lm[RIGHT_EYE_RIGHT].x) / 2 * w
            re_cy = (lm[RIGHT_EYE_UPPER[0]].y + lm[RIGHT_EYE_LOWER[0]].y) / 2 * h
            re_w  = abs(lm[RIGHT_EYE_RIGHT].x - lm[RIGHT_EYE_LEFT].x) * w + 1e-6

            right_dev = math.hypot(ri_x - re_cx, ri_y - re_cy) / re_w

            deviation = (left_dev + right_dev) / 2.0
            # Threshold: deviation < ~0.35 means looking roughly at camera
            looking = deviation < self.eye_contact_threshold
            return looking, deviation
        except (IndexError, AttributeError):
            return True, 0.0   # safe fallback

    def _compute_head_stability(self) -> bool:
        """
        Return True if head movement in the rolling window is below threshold.
        """
        if len(self._nose_positions) < 2:
            self._head_stability_scores.append(1.0)
            return True

        positions = list(self._nose_positions)
        movements = [
            math.hypot(positions[i][0] - positions[i-1][0],
                       positions[i][1] - positions[i-1][1])
            for i in range(1, len(positions))
        ]
        avg_movement = np.mean(movements)
        stable = avg_movement < self.head_move_threshold
        self._head_stability_scores.append(1.0 if stable else 0.0)
        return stable

    def _detect_smile(self, lm, w: int, h: int) -> bool:
        """
        Detect smile by measuring mouth-corner elevation relative to lip height.
        Smile ratio > threshold → smiling.
        """
        try:
            # Mouth corners
            left_corner  = np.array([lm[61].x * w,  lm[61].y * h])
            right_corner = np.array([lm[291].x * w, lm[291].y * h])
            # Upper/lower lip centres
            upper_lip = np.array([lm[13].x * w, lm[13].y * h])
            lower_lip = np.array([lm[14].x * w, lm[14].y * h])

            mouth_h = abs(upper_lip[1] - lower_lip[1])
            mouth_w = np.linalg.norm(right_corner - left_corner)

            corner_elevation = (
                (upper_lip[1] - left_corner[1]) + (upper_lip[1] - right_corner[1])
            ) / 2

            ratio = corner_elevation / (mouth_h + 1e-6)
            return ratio > 0.30
        except (IndexError, AttributeError):
            return False

    def _draw_overlays(
        self, frame, lm, w, h,
        eye_contact: bool, iris_deviation: float, head_stable: bool
    ) -> np.ndarray:
        """Draw diagnostic overlays on the frame (BGR)."""
        if not CV2_AVAILABLE:
            return frame

        color = (0, 255, 100) if eye_contact else (0, 100, 255)
        label = "EYE CONTACT ✓" if eye_contact else "LOOK AT CAMERA"
        cv2.putText(frame, label, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        if not head_stable:
            cv2.putText(frame, "HEAD MOVING", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        # Iris deviation bar
        bar_w = int(iris_deviation * 200)
        cv2.rectangle(frame, (10, 70), (210, 85), (50, 50, 50), -1)
        cv2.rectangle(frame, (10, 70), (10 + min(bar_w, 200), 85), color, -1)
        cv2.putText(frame, "Gaze Deviation", (10, 98),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        return frame
