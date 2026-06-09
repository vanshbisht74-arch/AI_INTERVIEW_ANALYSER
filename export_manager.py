"""
export_manager.py
-----------------
Exports interview data to CSV, JSON, and Excel-compatible formats.
Provides per-candidate and all-candidates export modes.
"""

import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from database_manager import DatabaseManager


class ExportManager:
    """
    Handles exporting interview history and scores to
    CSV / JSON / Excel formats for external analysis.
    """

    def __init__(self, db: DatabaseManager, export_dir: str = "reports"):
        self.db         = db
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    # ─── Public API ───────────────────────────────────────────────────────────

    def export_candidate_csv(self, candidate_id: int) -> str:
        """Export all sessions for one candidate to CSV."""
        rows  = self._build_rows(candidate_id=candidate_id)
        cand  = self.db.get_candidate(candidate_id)
        name  = (cand.get("name", "unknown") if cand else "unknown")
        fname = self._ts_filename(f"export_{name}", "csv")
        self._write_csv(rows, fname)
        return fname

    def export_all_csv(self) -> str:
        """Export all candidates / sessions to CSV."""
        rows  = self._build_rows()
        fname = self._ts_filename("export_all", "csv")
        self._write_csv(rows, fname)
        return fname

    def export_candidate_json(self, candidate_id: int) -> str:
        """Export one candidate's full history as JSON."""
        rows  = self._build_rows(candidate_id=candidate_id)
        cand  = self.db.get_candidate(candidate_id)
        name  = (cand.get("name", "unknown") if cand else "unknown")
        fname = self._ts_filename(f"export_{name}", "json")
        with open(fname, "w") as f:
            json.dump(rows, f, indent=2, default=str)
        return fname

    def export_all_json(self) -> str:
        """Export everything as JSON."""
        rows  = self._build_rows()
        fname = self._ts_filename("export_all", "json")
        with open(fname, "w") as f:
            json.dump(rows, f, indent=2, default=str)
        return fname

    def export_excel(self, candidate_id: Optional[int] = None) -> str:
        """
        Export to Excel (.xlsx) using pandas if available,
        otherwise fall back to CSV.
        """
        rows  = self._build_rows(candidate_id=candidate_id)
        suffix = f"_{self.db.get_candidate(candidate_id)['name']}" \
                 if candidate_id else "_all"
        fname_base = self._ts_filename(f"export{suffix}", "xlsx")

        if PANDAS_AVAILABLE:
            df = pd.DataFrame(rows)
            df.to_excel(fname_base, index=False, sheet_name="Interview History")
            return fname_base
        else:
            # Fall back to CSV
            fname_csv = fname_base.replace(".xlsx", ".csv")
            self._write_csv(rows, fname_csv)
            return fname_csv

    def export_summary_report(self, candidate_id: int) -> str:
        """
        Write a plain-text summary report for one candidate
        across all sessions.
        """
        cand = self.db.get_candidate(candidate_id)
        name = cand.get("name", "Unknown") if cand else "Unknown"
        stats = self.db.get_dashboard_stats(candidate_id)
        history = self.db.get_score_history(candidate_id)

        fname = self._ts_filename(f"summary_{name}", "txt")
        lines = [
            "=" * 60,
            f"  INTERVIEW PERFORMANCE SUMMARY — {name.upper()}",
            "=" * 60,
            f"  Generated : {datetime.now().strftime('%B %d, %Y %H:%M')}",
            "",
            "─── AGGREGATE STATS ──────────────────────────────────────",
            f"  Total Sessions   : {int(stats.get('total_interviews') or 0)}",
            f"  Average Score    : {stats.get('avg_overall') or 0:.1f}",
            f"  Best Score       : {stats.get('best_score') or 0:.1f}",
            f"  Avg Eye Contact  : {stats.get('avg_eye_contact') or 0:.1f}%",
            f"  Avg WPM          : {stats.get('avg_wpm') or 0:.1f}",
            f"  Avg Fillers/sess : {stats.get('avg_fillers') or 0:.1f}",
            "",
            "─── SESSION HISTORY ───────────────────────────────────────",
        ]
        for i, h in enumerate(history, 1):
            lines.append(
                f"  #{i:02d}  {(h.get('session_date') or '')[:16]}"
                f"  Overall: {h.get('overall_score') or 0:.0f}"
                f"  Eye: {h.get('eye_contact_score') or 0:.0f}"
                f"  Speech: {h.get('speech_score') or 0:.0f}"
            )
        lines += ["", "=" * 60]

        with open(fname, "w") as f:
            f.write("\n".join(lines))
        return fname

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _build_rows(self, candidate_id: Optional[int] = None) -> List[Dict]:
        """Build flat row dicts suitable for CSV / DataFrame."""
        if candidate_id:
            interviews = self.db.get_interviews_for_candidate(candidate_id)
            cand = self.db.get_candidate(candidate_id)
            cand_name = cand.get("name", "") if cand else ""
        else:
            interviews = self.db.get_all_interviews()
            cand_name  = None  # will be per-row

        rows = []
        for iv in interviews:
            iid    = iv["id"]
            scores = self.db.get_scores(iid) or {}
            row = {
                "interview_id":      iid,
                "candidate_name":    cand_name or iv.get("candidate_name", ""),
                "session_date":      iv.get("session_date", ""),
                "duration_sec":      iv.get("duration_sec", 0),
                "overall_score":     scores.get("overall_score",       0),
                "confidence_score":  scores.get("confidence_score",    0),
                "eye_contact_score": scores.get("eye_contact_score",   0),
                "communication_score": scores.get("communication_score", 0),
                "speech_score":      scores.get("speech_score",        0),
                "eye_contact_pct":   scores.get("eye_contact_pct",     0),
                "words_per_minute":  scores.get("words_per_minute",    0),
                "filler_word_count": scores.get("filler_word_count",   0),
                "speaking_time_sec": scores.get("speaking_time_sec",   0),
                "pause_count":       scores.get("pause_count",         0),
                "smile_percentage":  scores.get("smile_percentage",    0),
                "head_stability":    scores.get("head_stability",      0),
            }
            rows.append(row)
        return rows

    def _write_csv(self, rows: List[Dict], filepath: str):
        if not rows:
            with open(filepath, "w") as f:
                f.write("No data\n")
            return
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def _ts_filename(self, base: str, ext: str) -> str:
        safe  = "".join(c for c in base if c.isalnum() or c in "_-")
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(self.export_dir, f"{safe}_{ts}.{ext}")
        return fname
