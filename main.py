"""
main.py
-------
Entry point for the AI Interview Analyzer application.
Bootstraps the Tkinter GUI and performs a pre-flight dependency check.
"""

import sys
import os

# ─── Dependency check ─────────────────────────────────────────────────────────

REQUIRED = {
    "cv2":          "opencv-python",
    "mediapipe":    "mediapipe",
    "speech_recognition": "SpeechRecognition",
    "numpy":        "numpy",
    "pandas":       "pandas",
    "matplotlib":   "matplotlib",
    "reportlab":    "reportlab",
    "PIL":          "Pillow",
}

OPTIONAL = {
    "pyaudio": "PyAudio",
}

missing_required = []
missing_optional = []

for module, package in REQUIRED.items():
    try:
        __import__(module)
    except ImportError:
        missing_required.append(package)

for module, package in OPTIONAL.items():
    try:
        __import__(module)
    except ImportError:
        missing_optional.append(package)

if missing_required:
    print("=" * 60)
    print("  Missing required packages:")
    for p in missing_required:
        print(f"    pip install {p}")
    print("\n  Install all at once:")
    print("    pip install -r requirements.txt")
    print("=" * 60)
    # Continue anyway — modules handle ImportError gracefully

if missing_optional:
    print(f"[INFO] Optional packages not installed: {', '.join(missing_optional)}")
    print("       Microphone recording will use mock data.")
    print("       To enable: pip install " + " ".join(missing_optional))

# ─── Launch ───────────────────────────────────────────────────────────────────

def main():
    # Ensure working directory is project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Create required directories
    for d in ("assets", "reports", "recordings", "database"):
        os.makedirs(d, exist_ok=True)

    try:
        from gui import AIInterviewAnalyzerApp
        app = AIInterviewAnalyzerApp()
        app.mainloop()
    except Exception as e:
        import traceback
        print(f"\n[FATAL] Application crashed:\n{e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
