"""
database_manager.py
-------------------
Manages all SQLite database operations for the AI Interview Analyzer.
Handles candidates, interviews, scores, and reports tables.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class DatabaseManager:
    """
    Centralized database manager using SQLite.
    Implements singleton-like pattern for connection management.
    """

    def __init__(self, db_path: str = "database/interview.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.connection = None
        self._connect()
        self._initialize_schema()

    # ─── Connection ───────────────────────────────────────────────────────────

    def _connect(self):
        """Establish SQLite connection with WAL mode for performance."""
        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")

    def _get_cursor(self):
        """Return a cursor, reconnecting if needed."""
        try:
            self.connection.execute("SELECT 1")
        except (sqlite3.ProgrammingError, AttributeError):
            self._connect()
        return self.connection.cursor()

    # ─── Schema ───────────────────────────────────────────────────────────────

    def _initialize_schema(self):
        """Create all tables if they do not exist."""
        cursor = self._get_cursor()

        # Candidates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                email       TEXT    UNIQUE,
                created_at  TEXT    DEFAULT (datetime('now')),
                updated_at  TEXT    DEFAULT (datetime('now'))
            )
        """)

        # Interviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id    INTEGER NOT NULL REFERENCES candidates(id),
                session_date    TEXT    DEFAULT (datetime('now')),
                duration_sec    REAL    DEFAULT 0,
                recording_path  TEXT,
                status          TEXT    DEFAULT 'completed',
                notes           TEXT
            )
        """)

        # Scores table – one row per interview
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id        INTEGER NOT NULL REFERENCES interviews(id),
                confidence_score    REAL    DEFAULT 0,
                eye_contact_score   REAL    DEFAULT 0,
                communication_score REAL    DEFAULT 0,
                speech_score        REAL    DEFAULT 0,
                overall_score       REAL    DEFAULT 0,
                eye_contact_pct     REAL    DEFAULT 0,
                words_per_minute    REAL    DEFAULT 0,
                filler_word_count   INTEGER DEFAULT 0,
                speaking_time_sec   REAL    DEFAULT 0,
                pause_count         INTEGER DEFAULT 0,
                smile_percentage    REAL    DEFAULT 0,
                head_stability      REAL    DEFAULT 0,
                raw_metrics         TEXT                        -- JSON blob
            )
        """)

        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id    INTEGER NOT NULL REFERENCES interviews(id),
                report_path     TEXT,
                generated_at    TEXT    DEFAULT (datetime('now')),
                strengths       TEXT,                           -- JSON list
                improvements    TEXT                            -- JSON list
            )
        """)

        self.connection.commit()

    # ─── Candidate CRUD ───────────────────────────────────────────────────────

    def add_candidate(self, name: str, email: str = "") -> int:
        """Insert a new candidate and return its id."""
        cursor = self._get_cursor()
        cursor.execute(
            "INSERT INTO candidates (name, email) VALUES (?, ?)",
            (name, email)
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_candidate(self, candidate_id: int) -> Optional[Dict]:
        """Fetch a single candidate by id."""
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_candidates(self) -> List[Dict]:
        """Return all candidates."""
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM candidates ORDER BY name")
        return [dict(r) for r in cursor.fetchall()]

    def get_or_create_candidate(self, name: str, email: str = "") -> int:
        """Return existing candidate id or create a new one."""
        cursor = self._get_cursor()
        cursor.execute("SELECT id FROM candidates WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row["id"]
        return self.add_candidate(name, email)

    # ─── Interview CRUD ───────────────────────────────────────────────────────

    def create_interview(self, candidate_id: int, recording_path: str = "") -> int:
        """Create a new interview record and return its id."""
        cursor = self._get_cursor()
        cursor.execute(
            "INSERT INTO interviews (candidate_id, recording_path) VALUES (?, ?)",
            (candidate_id, recording_path)
        )
        self.connection.commit()
        return cursor.lastrowid

    def update_interview_duration(self, interview_id: int, duration_sec: float):
        """Update the duration of an interview session."""
        cursor = self._get_cursor()
        cursor.execute(
            "UPDATE interviews SET duration_sec = ? WHERE id = ?",
            (duration_sec, interview_id)
        )
        self.connection.commit()

    def get_interview(self, interview_id: int) -> Optional[Dict]:
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_interviews_for_candidate(self, candidate_id: int) -> List[Dict]:
        """Return all interviews for a candidate, newest first."""
        cursor = self._get_cursor()
        cursor.execute(
            """
            SELECT i.*, s.overall_score, s.confidence_score
            FROM interviews i
            LEFT JOIN scores s ON s.interview_id = i.id
            WHERE i.candidate_id = ?
            ORDER BY i.session_date DESC
            """,
            (candidate_id,)
        )
        return [dict(r) for r in cursor.fetchall()]

    def get_all_interviews(self) -> List[Dict]:
        """Return all interviews with candidate name."""
        cursor = self._get_cursor()
        cursor.execute(
            """
            SELECT i.*, c.name AS candidate_name, s.overall_score
            FROM interviews i
            JOIN candidates c ON c.id = i.candidate_id
            LEFT JOIN scores s ON s.interview_id = i.id
            ORDER BY i.session_date DESC
            """
        )
        return [dict(r) for r in cursor.fetchall()]

    # ─── Scores CRUD ──────────────────────────────────────────────────────────

    def save_scores(self, interview_id: int, scores: Dict[str, Any]):
        """Insert or replace the score record for an interview."""
        cursor = self._get_cursor()
        raw = json.dumps(scores.get("raw_metrics", {}))

        cursor.execute(
            """
            INSERT OR REPLACE INTO scores (
                interview_id, confidence_score, eye_contact_score,
                communication_score, speech_score, overall_score,
                eye_contact_pct, words_per_minute, filler_word_count,
                speaking_time_sec, pause_count, smile_percentage,
                head_stability, raw_metrics
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                interview_id,
                scores.get("confidence_score", 0),
                scores.get("eye_contact_score", 0),
                scores.get("communication_score", 0),
                scores.get("speech_score", 0),
                scores.get("overall_score", 0),
                scores.get("eye_contact_pct", 0),
                scores.get("words_per_minute", 0),
                scores.get("filler_word_count", 0),
                scores.get("speaking_time_sec", 0),
                scores.get("pause_count", 0),
                scores.get("smile_percentage", 0),
                scores.get("head_stability", 0),
                raw
            )
        )
        self.connection.commit()

    def get_scores(self, interview_id: int) -> Optional[Dict]:
        cursor = self._get_cursor()
        cursor.execute("SELECT * FROM scores WHERE interview_id = ?", (interview_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["raw_metrics"] = json.loads(d.get("raw_metrics") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["raw_metrics"] = {}
        return d

    def get_score_history(self, candidate_id: int) -> List[Dict]:
        """Return scores across all interviews for trend analysis."""
        cursor = self._get_cursor()
        cursor.execute(
            """
            SELECT i.session_date, s.*
            FROM scores s
            JOIN interviews i ON i.id = s.interview_id
            WHERE i.candidate_id = ?
            ORDER BY i.session_date ASC
            """,
            (candidate_id,)
        )
        return [dict(r) for r in cursor.fetchall()]

    # ─── Reports CRUD ─────────────────────────────────────────────────────────

    def save_report(
        self,
        interview_id: int,
        report_path: str,
        strengths: List[str],
        improvements: List[str]
    ):
        cursor = self._get_cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO reports
                (interview_id, report_path, strengths, improvements)
            VALUES (?,?,?,?)
            """,
            (
                interview_id,
                report_path,
                json.dumps(strengths),
                json.dumps(improvements)
            )
        )
        self.connection.commit()

    def get_report(self, interview_id: int) -> Optional[Dict]:
        cursor = self._get_cursor()
        cursor.execute(
            "SELECT * FROM reports WHERE interview_id = ?",
            (interview_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["strengths"] = json.loads(d.get("strengths") or "[]")
            d["improvements"] = json.loads(d.get("improvements") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["strengths"] = []
            d["improvements"] = []
        return d

    def get_all_reports(self) -> List[Dict]:
        cursor = self._get_cursor()
        cursor.execute(
            """
            SELECT r.*, c.name AS candidate_name, i.session_date,
                   s.overall_score
            FROM reports r
            JOIN interviews i ON i.id = r.interview_id
            JOIN candidates c ON c.id = i.candidate_id
            LEFT JOIN scores s ON s.interview_id = i.id
            ORDER BY r.generated_at DESC
            """
        )
        rows = []
        for row in cursor.fetchall():
            d = dict(row)
            try:
                d["strengths"] = json.loads(d.get("strengths") or "[]")
                d["improvements"] = json.loads(d.get("improvements") or "[]")
            except (json.JSONDecodeError, TypeError):
                d["strengths"] = []
                d["improvements"] = []
            rows.append(d)
        return rows

    # ─── Analytics helpers ────────────────────────────────────────────────────

    def get_dashboard_stats(self, candidate_id: int) -> Dict:
        """Return aggregated statistics for the analytics dashboard."""
        cursor = self._get_cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*)          AS total_interviews,
                AVG(s.overall_score)     AS avg_overall,
                MAX(s.overall_score)     AS best_score,
                AVG(s.eye_contact_pct)   AS avg_eye_contact,
                AVG(s.words_per_minute)  AS avg_wpm,
                AVG(s.filler_word_count) AS avg_fillers
            FROM interviews i
            LEFT JOIN scores s ON s.interview_id = i.id
            WHERE i.candidate_id = ?
            """,
            (candidate_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else {}

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
