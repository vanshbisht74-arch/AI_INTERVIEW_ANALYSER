"""
filler_word_detector.py
------------------------
Detects filler words in transcribed speech.
Maintains counts per word and per session.
"""

import re
from collections import Counter
from typing import Dict, List, Tuple


# Canonical set of filler words/phrases to detect
FILLER_WORDS = [
    "um", "uh", "like", "basically", "actually",
    "you know", "literally", "right", "so", "well",
    "kind of", "sort of", "i mean", "you see",
]


class FillerWordDetector:
    """
    Scans speech transcriptions for filler words and returns
    per-word counts and total penalty scores.
    """

    def __init__(self, custom_fillers: List[str] = None):
        self._fillers = list(FILLER_WORDS)
        if custom_fillers:
            self._fillers.extend(custom_fillers)
        # Deduplicate and sort longest first (greedy multi-word match)
        self._fillers = sorted(set(f.lower() for f in self._fillers), key=len, reverse=True)

        # Session-level accumulator
        self._session_counts: Counter = Counter()

    # ─── Public API ───────────────────────────────────────────────────────────

    def analyze_text(self, text: str) -> Dict:
        """
        Scan a single transcript segment for filler words.

        Returns:
            {
              "total": int,
              "counts": {word: count, ...},
              "marked_text": str   # original text with fillers wrapped
            }
        """
        if not text or not text.strip():
            return {"total": 0, "counts": {}, "marked_text": text or ""}

        text_lower = text.lower()
        counts: Counter = Counter()

        for filler in self._fillers:
            # Match whole-word / whole-phrase occurrences
            pattern = r'\b' + re.escape(filler) + r'\b'
            matches = re.findall(pattern, text_lower)
            if matches:
                counts[filler] += len(matches)

        total = sum(counts.values())
        self._session_counts.update(counts)

        marked = self._mark_fillers(text, counts)
        return {"total": total, "counts": dict(counts), "marked_text": marked}

    def get_session_totals(self) -> Dict:
        """Return cumulative counts for the full interview session."""
        return {
            "total": sum(self._session_counts.values()),
            "counts": dict(self._session_counts),
            "top_3": self._session_counts.most_common(3),
        }

    def get_filler_penalty(self) -> float:
        """
        Return a 0-100 score where 100 = zero fillers.
        Penalty increases with filler density.
        """
        total = sum(self._session_counts.values())
        if total == 0:
            return 100.0
        # Each filler subtracts ~3 points, floor at 0
        penalty = min(100, total * 3)
        return max(0.0, 100.0 - penalty)

    def reset(self):
        """Clear session-level accumulator."""
        self._session_counts.clear()

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _mark_fillers(self, text: str, counts: Counter) -> str:
        """
        Return text with detected fillers surrounded by [FILLER: word].
        Case-insensitive replacement preserving original casing.
        """
        marked = text
        for filler in counts:
            pattern = re.compile(r'\b' + re.escape(filler) + r'\b', re.IGNORECASE)
            marked = pattern.sub(f"[FILLER:{filler.upper()}]", marked)
        return marked

    # ─── Static helpers ───────────────────────────────────────────────────────

    @staticmethod
    def get_filler_list() -> List[str]:
        return list(FILLER_WORDS)
