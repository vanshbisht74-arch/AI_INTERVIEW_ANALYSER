"""
settings_manager.py
--------------------
Manages application configuration using a JSON settings file.
Provides defaults and persists user preferences.
"""

import json
import os
from typing import Any, Dict


class SettingsManager:
    """
    Reads/writes application settings to a JSON file.
    Provides type-safe getters with fallback defaults.
    """

    DEFAULTS: Dict[str, Any] = {
        # Camera
        "camera_index": 0,
        "frame_width": 640,
        "frame_height": 480,
        "camera_fps": 30,

        # Audio
        "audio_sample_rate": 16000,
        "audio_channels": 1,
        "audio_chunk_size": 1024,
        "silence_threshold": 500,           # RMS amplitude
        "silence_duration_sec": 1.5,        # pause if silent this long

        # Analysis thresholds
        "eye_contact_threshold": 0.65,      # iris ratio for "looking at camera"
        "blink_threshold": 0.25,            # EAR value
        "smile_threshold": 0.30,            # mouth curvature ratio
        "head_movement_threshold": 15,      # pixels of movement before "unstable"
        "ideal_wpm_min": 120,
        "ideal_wpm_max": 160,

        # Scoring weights (must sum to 1.0)
        "weight_eye_contact": 0.25,
        "weight_speech_speed": 0.20,
        "weight_filler_words": 0.20,
        "weight_facial_stability": 0.20,
        "weight_speaking_consistency": 0.15,

        # Report
        "reports_dir": "reports",
        "recordings_dir": "recordings",

        # UI
        "theme": "dark",
        "accent_color": "#00D4FF",
        "app_title": "AI Interview Analyzer",
        "default_candidate": "",

        # Speech recognition
        "speech_language": "en-US",
        "use_google_speech": True,
    }

    def __init__(self, settings_path: str = "settings.json"):
        self.settings_path = settings_path
        self._settings: Dict[str, Any] = {}
        self._load()

    # ─── Load / Save ──────────────────────────────────────────────────────────

    def _load(self):
        """Load settings from file, falling back to defaults."""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    stored = json.load(f)
                # Merge: defaults + stored overrides
                self._settings = {**self.DEFAULTS, **stored}
            except (json.JSONDecodeError, IOError):
                self._settings = dict(self.DEFAULTS)
        else:
            self._settings = dict(self.DEFAULTS)

    def save(self):
        """Persist current settings to disk."""
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self._settings, f, indent=2)
        except IOError as e:
            print(f"[SettingsManager] Could not save settings: {e}")

    # ─── Getters / Setters ────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        self._settings[key] = value
        self.save()

    def get_all(self) -> Dict[str, Any]:
        return dict(self._settings)

    def reset_to_defaults(self):
        self._settings = dict(self.DEFAULTS)
        self.save()

    # ─── Convenience properties ───────────────────────────────────────────────

    @property
    def camera_index(self) -> int:
        return int(self.get("camera_index", 0))

    @property
    def frame_width(self) -> int:
        return int(self.get("frame_width", 640))

    @property
    def frame_height(self) -> int:
        return int(self.get("frame_height", 480))

    @property
    def audio_sample_rate(self) -> int:
        return int(self.get("audio_sample_rate", 16000))

    @property
    def silence_threshold(self) -> int:
        return int(self.get("silence_threshold", 500))

    @property
    def silence_duration_sec(self) -> float:
        return float(self.get("silence_duration_sec", 1.5))

    @property
    def ideal_wpm_min(self) -> int:
        return int(self.get("ideal_wpm_min", 120))

    @property
    def ideal_wpm_max(self) -> int:
        return int(self.get("ideal_wpm_max", 160))

    @property
    def reports_dir(self) -> str:
        d = self.get("reports_dir", "reports")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def recordings_dir(self) -> str:
        d = self.get("recordings_dir", "recordings")
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def theme(self) -> str:
        return self.get("theme", "dark")

    @property
    def accent_color(self) -> str:
        return self.get("accent_color", "#00D4FF")
