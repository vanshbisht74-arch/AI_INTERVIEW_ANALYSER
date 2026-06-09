"""
confidence_calculator.py
-------------------------
Computes the overall confidence score and sub-scores from raw metrics.
All scores are on a 0-100 scale.
"""

from typing import Dict


class ConfidenceCalculator:
    """
    Aggregates eye-contact, speech, filler-word, facial-stability,
    and speaking-consistency metrics into a single Confidence Score
    and a set of sub-scores for the dashboard.
    """

    # Default weights (must sum to 1.0)
    DEFAULT_WEIGHTS = {
        "eye_contact":          0.25,
        "speech_speed":         0.20,
        "filler_words":         0.20,
        "facial_stability":     0.20,
        "speaking_consistency": 0.15,
    }

    def __init__(self, settings=None):
        if settings:
            self.weights = {
                "eye_contact":          settings.get("weight_eye_contact",          0.25),
                "speech_speed":         settings.get("weight_speech_speed",         0.20),
                "filler_words":         settings.get("weight_filler_words",         0.20),
                "facial_stability":     settings.get("weight_facial_stability",     0.20),
                "speaking_consistency": settings.get("weight_speaking_consistency", 0.15),
            }
        else:
            self.weights = dict(self.DEFAULT_WEIGHTS)

    # ─── Public API ───────────────────────────────────────────────────────────

    def calculate(
        self,
        eye_contact_pct: float,
        words_per_minute: float,
        filler_word_count: int,
        head_stability: float,   # 0-1 ratio
        smile_percentage: float,
        speaking_time_sec: float,
        total_session_sec: float,
        pause_count: int,
    ) -> Dict[str, float]:
        """
        Compute all scores and return a dict with:
          confidence_score, eye_contact_score, communication_score,
          speech_score, overall_score
        """
        # ── Component scores ──────────────────────────────────────────────────
        eye_score        = self._eye_contact_score(eye_contact_pct)
        speech_score     = self._speech_speed_score(words_per_minute)
        filler_score     = self._filler_score(filler_word_count, speaking_time_sec)
        stability_score  = self._facial_stability_score(head_stability, smile_percentage)
        consistency_score = self._speaking_consistency_score(
            speaking_time_sec, total_session_sec, pause_count
        )

        # ── Weighted confidence score ─────────────────────────────────────────
        confidence = (
            eye_score        * self.weights["eye_contact"] +
            speech_score     * self.weights["speech_speed"] +
            filler_score     * self.weights["filler_words"] +
            stability_score  * self.weights["facial_stability"] +
            consistency_score * self.weights["speaking_consistency"]
        )

        # ── Dashboard sub-scores ──────────────────────────────────────────────
        # Communication = blend of filler + consistency
        communication = (filler_score * 0.55 + consistency_score * 0.45)
        # Overall = slight boost for high eye-contact
        overall = confidence * 0.90 + eye_score * 0.10

        return {
            "confidence_score":    round(min(100.0, max(0.0, confidence)), 1),
            "eye_contact_score":   round(min(100.0, max(0.0, eye_score)), 1),
            "communication_score": round(min(100.0, max(0.0, communication)), 1),
            "speech_score":        round(min(100.0, max(0.0, speech_score)), 1),
            "overall_score":       round(min(100.0, max(0.0, overall)), 1),
            # Raw components for transparency
            "_filler_score":       round(filler_score, 1),
            "_stability_score":    round(stability_score, 1),
            "_consistency_score":  round(consistency_score, 1),
        }

    def generate_strengths_and_improvements(self, scores: Dict, metrics: Dict) -> Dict:
        """
        Return human-readable lists of strengths and areas for improvement
        based on computed scores and raw metrics.
        """
        strengths    = []
        improvements = []

        # Eye contact
        if scores["eye_contact_score"] >= 75:
            strengths.append("Excellent eye contact — you project confidence and engagement.")
        elif scores["eye_contact_score"] >= 55:
            strengths.append("Decent eye contact maintained throughout the session.")
        else:
            improvements.append(
                "Work on maintaining consistent eye contact with the camera; "
                "it signals confidence to interviewers."
            )

        # Speech speed
        wpm = metrics.get("words_per_minute", 0)
        if 120 <= wpm <= 160:
            strengths.append(f"Great speaking pace ({wpm:.0f} WPM) — clear and easy to follow.")
        elif wpm < 100:
            improvements.append(
                f"Your speaking pace ({wpm:.0f} WPM) is slow. "
                "Aim for 120-160 WPM to sound more energetic."
            )
        elif wpm > 180:
            improvements.append(
                f"You spoke quite fast ({wpm:.0f} WPM). "
                "Slow down slightly to let key points land."
            )

        # Filler words
        fillers = metrics.get("filler_word_count", 0)
        if fillers == 0:
            strengths.append("Zero filler words detected — very polished delivery.")
        elif fillers <= 5:
            strengths.append(f"Minimal filler words ({fillers}) — good verbal discipline.")
        elif fillers <= 15:
            improvements.append(
                f"{fillers} filler words detected (um, uh, like, etc.). "
                "Practice pausing instead of filling silence."
            )
        else:
            improvements.append(
                f"High filler word count ({fillers}). Record yourself and practice "
                "replacing fillers with deliberate pauses."
            )

        # Facial stability
        if scores["_stability_score"] >= 80:
            strengths.append("Calm, stable facial presence throughout the interview.")
        elif scores["_stability_score"] < 55:
            improvements.append(
                "Frequent head movement was detected. Try to keep your head "
                "still and use purposeful nods."
            )

        # Speaking consistency
        if scores["_consistency_score"] >= 75:
            strengths.append("Consistent speaking rhythm — you filled the session well.")
        elif scores["_consistency_score"] < 50:
            improvements.append(
                "Long silences were detected. Prepare structured answers "
                "(STAR method) to reduce pausing."
            )

        # Overall confidence
        if scores["confidence_score"] >= 80:
            strengths.append("High overall confidence score — strong interview performance!")
        elif scores["confidence_score"] >= 60:
            pass  # No specific message at mid range
        else:
            improvements.append(
                "Overall confidence score is below 60. Focus on the areas above "
                "and practise with mock interviews regularly."
            )

        # Ensure at least one entry in each list
        if not strengths:
            strengths.append("You completed the session — every practice makes you better!")
        if not improvements:
            improvements.append("Continue practising to maintain your excellent performance.")

        return {"strengths": strengths, "improvements": improvements}

    # ─── Component score helpers ──────────────────────────────────────────────

    def _eye_contact_score(self, pct: float) -> float:
        """Ideal eye contact 65-85%. Penalise extremes."""
        if pct >= 65:
            return min(100.0, 70 + (pct - 65) * 1.5)
        return max(0.0, pct * 1.05)

    def _speech_speed_score(self, wpm: float) -> float:
        """Score based on proximity to ideal WPM range."""
        if wpm <= 0:
            return 0.0
        if 120 <= wpm <= 160:
            return 100.0
        elif wpm < 120:
            return max(0.0, (wpm / 120) * 90)
        else:  # wpm > 160
            excess = wpm - 160
            return max(0.0, 100 - excess * 0.6)

    def _filler_score(self, count: int, speaking_sec: float) -> float:
        """Penalise fillers; scale by speaking duration."""
        if speaking_sec <= 0:
            return 50.0
        # Fillers per minute
        fpm = (count / speaking_sec) * 60
        if fpm == 0:
            return 100.0
        return max(0.0, 100 - fpm * 8)

    def _facial_stability_score(self, stability_ratio: float, smile_pct: float) -> float:
        """Stability 0-1; smile adds a small bonus."""
        base = stability_ratio * 85
        smile_bonus = min(15, smile_pct * 0.3)
        return min(100.0, base + smile_bonus)

    def _speaking_consistency_score(
        self, speaking_sec: float, total_sec: float, pause_count: int
    ) -> float:
        """Ratio of speaking time to session time, minus pause penalty."""
        if total_sec <= 0:
            return 50.0
        ratio = speaking_sec / total_sec
        ratio_score = min(100.0, ratio * 130)  # 77% speaking → 100
        pause_penalty = min(30, pause_count * 3)
        return max(0.0, ratio_score - pause_penalty)
