"""
profile_manager.py
------------------
Multi-candidate profile management.
Provides CRUD for candidate profiles with avatar initials,
session history summary, and quick-switch between profiles.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from database_manager import DatabaseManager


class CandidateProfile:
    """Value object representing a full candidate profile."""

    def __init__(self, data: Dict):
        self.id         = data.get("id", 0)
        self.name       = data.get("name", "")
        self.email      = data.get("email", "")
        self.created_at = data.get("created_at", "")

        # Session stats (joined from DB)
        self.total_sessions  = data.get("total_sessions",  0)
        self.best_score      = data.get("best_score",      0.0)
        self.latest_score    = data.get("latest_score",    0.0)
        self.avg_score       = data.get("avg_score",       0.0)
        self.improvement_pct = data.get("improvement_pct", 0.0)  # first vs last

    @property
    def initials(self) -> str:
        """Return up to 2-letter initials for avatar display."""
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.name[:2].upper() if self.name else "??"

    @property
    def avatar_color(self) -> str:
        """Deterministic accent color based on name hash."""
        colors = [
            "#00D4FF", "#7C3AED", "#3FB950", "#F78166",
            "#E3B341", "#58A6FF", "#FF79C6", "#50FA7B",
        ]
        idx = hash(self.name) % len(colors)
        return colors[idx]

    @property
    def trend_arrow(self) -> str:
        if self.improvement_pct > 5:
            return "↑"
        elif self.improvement_pct < -5:
            return "↓"
        return "→"

    @property
    def trend_color(self) -> str:
        if self.improvement_pct > 5:
            return "#3FB950"
        elif self.improvement_pct < -5:
            return "#F78166"
        return "#E3B341"

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "email": self.email,
            "total_sessions": self.total_sessions,
            "best_score": self.best_score,
            "latest_score": self.latest_score,
            "avg_score": self.avg_score,
            "improvement_pct": self.improvement_pct,
        }


class ProfileManager:
    """
    Manages candidate profiles.
    Wraps DatabaseManager with profile-specific aggregation queries.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    # ─── Profile CRUD ─────────────────────────────────────────────────────────

    def create_profile(self, name: str, email: str = "") -> CandidateProfile:
        """Create a new candidate and return their profile."""
        if not name.strip():
            raise ValueError("Candidate name cannot be empty.")
        candidate_id = self.db.add_candidate(name.strip(), email.strip())
        return self.get_profile(candidate_id)

    def get_profile(self, candidate_id: int) -> Optional[CandidateProfile]:
        """Load a full profile including aggregated stats."""
        candidate = self.db.get_candidate(candidate_id)
        if not candidate:
            return None
        stats = self._aggregate_stats(candidate_id)
        return CandidateProfile({**candidate, **stats})

    def get_all_profiles(self) -> List[CandidateProfile]:
        """Return all profiles with aggregated stats, sorted by name."""
        candidates = self.db.get_all_candidates()
        profiles   = []
        for c in candidates:
            stats = self._aggregate_stats(c["id"])
            profiles.append(CandidateProfile({**c, **stats}))
        return sorted(profiles, key=lambda p: p.name.lower())

    def get_or_create_profile(self, name: str, email: str = "") -> CandidateProfile:
        """Return existing profile or create one."""
        cid = self.db.get_or_create_candidate(name, email)
        return self.get_profile(cid)

    def delete_profile(self, candidate_id: int) -> bool:
        """
        Remove a candidate and all their data.
        Returns True on success.
        """
        cursor = self.db._get_cursor()
        try:
            # Cascade via foreign keys (FK enforcement is ON)
            # Delete scores → reports → interviews → candidate
            cursor.execute(
                """
                DELETE FROM scores WHERE interview_id IN
                    (SELECT id FROM interviews WHERE candidate_id = ?)
                """, (candidate_id,)
            )
            cursor.execute(
                """
                DELETE FROM reports WHERE interview_id IN
                    (SELECT id FROM interviews WHERE candidate_id = ?)
                """, (candidate_id,)
            )
            cursor.execute(
                "DELETE FROM interviews WHERE candidate_id = ?",
                (candidate_id,)
            )
            cursor.execute(
                "DELETE FROM candidates WHERE id = ?",
                (candidate_id,)
            )
            self.db.connection.commit()
            return True
        except Exception as e:
            print(f"[ProfileManager] Delete error: {e}")
            self.db.connection.rollback()
            return False

    def update_profile(
        self, candidate_id: int, name: str = None, email: str = None
    ) -> Optional[CandidateProfile]:
        """Update name/email for an existing candidate."""
        cursor = self.db._get_cursor()
        if name is not None:
            cursor.execute(
                "UPDATE candidates SET name=?, updated_at=datetime('now') WHERE id=?",
                (name.strip(), candidate_id)
            )
        if email is not None:
            cursor.execute(
                "UPDATE candidates SET email=?, updated_at=datetime('now') WHERE id=?",
                (email.strip(), candidate_id)
            )
        self.db.connection.commit()
        return self.get_profile(candidate_id)

    # ─── Session history ──────────────────────────────────────────────────────

    def get_session_history(self, candidate_id: int) -> List[Dict]:
        """Return all sessions for a candidate, newest first, with scores."""
        return self.db.get_interviews_for_candidate(candidate_id)

    def get_improvement_trend(self, candidate_id: int) -> List[Dict]:
        """
        Return a list of {date, overall_score} dicts for trend charting.
        """
        history = self.db.get_score_history(candidate_id)
        return [
            {
                "date":          h.get("session_date", "")[:10],
                "overall_score": h.get("overall_score", 0),
                "eye_score":     h.get("eye_contact_score", 0),
                "speech_score":  h.get("speech_score", 0),
            }
            for h in history
        ]

    # ─── Aggregation ──────────────────────────────────────────────────────────

    def _aggregate_stats(self, candidate_id: int) -> Dict:
        """Compute aggregated stats for one candidate."""
        history = self.db.get_score_history(candidate_id)
        if not history:
            return {
                "total_sessions": 0, "best_score": 0.0,
                "latest_score": 0.0, "avg_score": 0.0,
                "improvement_pct": 0.0,
            }

        scores = [h.get("overall_score", 0) or 0 for h in history]
        best   = max(scores)
        avg    = sum(scores) / len(scores)
        latest = scores[-1]

        # Improvement: compare first half avg vs second half avg
        if len(scores) >= 4:
            mid  = len(scores) // 2
            first_avg  = sum(scores[:mid]) / mid
            second_avg = sum(scores[mid:]) / (len(scores) - mid)
            impr = ((second_avg - first_avg) / max(first_avg, 1)) * 100
        elif len(scores) >= 2:
            impr = ((scores[-1] - scores[0]) / max(scores[0], 1)) * 100
        else:
            impr = 0.0

        return {
            "total_sessions":  len(scores),
            "best_score":      round(best, 1),
            "latest_score":    round(latest, 1),
            "avg_score":       round(avg, 1),
            "improvement_pct": round(impr, 1),
        }
