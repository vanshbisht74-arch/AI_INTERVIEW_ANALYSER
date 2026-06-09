# 🎯 AI Interview Analyzer

> A production-grade desktop application that analyzes mock interviews in real time using computer vision, speech recognition, and AI scoring — then generates a detailed PDF performance report.

---

## 📸 Features

| Module | What it does |
|---|---|
| **Eye Contact Analyzer** | MediaPipe Face Mesh tracks iris position, blink rate, and head stability every frame |
| **Speech Analyzer** | PyAudio + SpeechRecognition capture and transcribe audio; measures WPM, pauses, speaking time |
| **Filler Word Detector** | Scans transcripts for *um, uh, like, basically, actually, you know, literally* and more |
| **Confidence Calculator** | Weighted aggregation of all signals → single 0–100 score |
| **PDF Report Generator** | ReportLab-powered professional report with score cards, trend bars, strengths & improvements |
| **Analytics Dashboard** | Matplotlib charts embedded in Tkinter — trend lines, bar charts, progress over time |
| **SQLite Database** | Full persistence: candidates, interviews, scores, reports |
| **Multi-page GUI** | Home · Interview Session · Analytics · Reports · Settings |

---

## 🗂 Project Structure

```
ai_interview_analyzer/
├── main.py                  # Entry point & dependency check
├── gui.py                   # Tkinter multi-page application
├── interview_manager.py     # Session orchestrator
├── eye_contact_analyzer.py  # MediaPipe face + gaze analysis
├── speech_analyzer.py       # Audio capture + speech recognition
├── filler_word_detector.py  # Filler word scanning
├── confidence_calculator.py # Score aggregation
├── report_generator.py      # PDF / text report builder
├── analytics_dashboard.py   # Matplotlib charts
├── database_manager.py      # SQLite ORM layer
├── settings_manager.py      # JSON settings persistence
├── requirements.txt
├── assets/                  # App assets (icons, etc.)
├── reports/                 # Generated PDF reports (auto-created)
├── recordings/              # WAV audio recordings (auto-created)
└── database/
    └── interview.db         # SQLite database (auto-created)
```

---

## ⚙️ Installation

### Prerequisites
- Python 3.9 – 3.11 (recommended: 3.10)
- A webcam
- A microphone
- ~500 MB disk space (mostly MediaPipe models)

### Step 1 — Clone / download the project

```bash
git clone https://github.com/yourname/ai-interview-analyzer.git
cd ai-interview-analyzer
```

### Step 2 — Create a virtual environment (recommended)

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Windows note:** If PyAudio fails to install, download the pre-built wheel from  
> https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio and install with:  
> `pip install PyAudio‑0.2.14‑cp310‑cp310‑win_amd64.whl`

> **Linux note:** You may need:  
> `sudo apt-get install portaudio19-dev python3-pyaudio`

> **macOS note:**  
> `brew install portaudio && pip install pyaudio`

---

## ▶️ Running the Application

```bash
python main.py
```

The app will:
1. Check for missing dependencies and warn you.
2. Create `reports/`, `recordings/`, and `database/` directories automatically.
3. Open the GUI window.

---

## 🖥 Usage Guide

### 1. Set Candidate Name
In the left sidebar, type your name in the **Candidate** field and click **Set Candidate**.

### 2. Start an Interview
- Click **Interview** in the sidebar.
- Click **▶ Start Interview**.
- Your webcam feed will appear with live eye-contact overlays.
- Speak naturally — the live transcript updates in real time.

### 3. Stop and Review
- Click **⏹ Stop Interview**.
- The system calculates all scores and generates your PDF report.
- A summary dialog shows your scores.

### 4. View Analytics
- Click **Analytics** to see trend charts across all your sessions.

### 5. Browse Reports
- Click **Reports** to see all saved reports.
- Double-click any row to open the PDF.

### 6. Adjust Settings
- Click **Settings** to tune thresholds, camera index, audio settings, and score weights.

---

## 📊 Scoring System

```
Confidence Score = weighted average of:
  ├── Eye Contact Score       × 0.25
  ├── Speech Speed Score      × 0.20
  ├── Filler Word Score       × 0.20
  ├── Facial Stability Score  × 0.20
  └── Speaking Consistency    × 0.15

Eye Contact Score   → % frames where iris deviation < threshold
Speech Speed Score  → proximity of WPM to 120-160 ideal range
Filler Word Score   → 100 - (fillers_per_minute × 8)
Facial Stability    → head stability ratio + smile bonus
Speaking Consistency→ speaking_time / session_time - pause penalty

Overall Score = Confidence × 0.90 + Eye Contact × 0.10
```

---

## 🗄 Database Schema

```sql
-- Candidates
candidates(id, name, email, created_at, updated_at)

-- Interview sessions
interviews(id, candidate_id, session_date, duration_sec,
           recording_path, status, notes)

-- Per-session scores
scores(id, interview_id, confidence_score, eye_contact_score,
       communication_score, speech_score, overall_score,
       eye_contact_pct, words_per_minute, filler_word_count,
       speaking_time_sec, pause_count, smile_percentage,
       head_stability, raw_metrics)

-- Generated reports
reports(id, interview_id, report_path, generated_at,
        strengths, improvements)
```

---

## 🔧 Configuration

All settings are stored in `settings.json` (auto-created on first run).  
You can edit them via the Settings page in the GUI or directly in the JSON file.

Key settings:

| Setting | Default | Description |
|---|---|---|
| `camera_index` | `0` | Webcam index (0 = default camera) |
| `ideal_wpm_min` | `120` | Minimum ideal speaking speed |
| `ideal_wpm_max` | `160` | Maximum ideal speaking speed |
| `eye_contact_threshold` | `0.65` | Iris deviation ratio for "looking at camera" |
| `silence_threshold` | `500` | RMS amplitude below which audio is considered silence |
| `silence_duration_sec` | `1.5` | Seconds of silence before counting as a pause |

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| GUI | Python Tkinter (built-in, no browser needed) |
| Computer Vision | OpenCV 4.9, MediaPipe 0.10 |
| Speech | SpeechRecognition 3.10, PyAudio 0.2 |
| Numerics | NumPy, Pandas |
| Charts | Matplotlib 3.8 |
| PDF | ReportLab 4.1 |
| Database | SQLite3 (built-in) |
| Images | Pillow 10 |

---

## 🛠 Troubleshooting

**Camera not opening**  
→ Change `camera_index` in Settings (try 1, 2, etc.)

**No audio captured / mock data used**  
→ Install PyAudio: `pip install pyaudio`  
→ Check microphone permissions on macOS/Windows

**Speech recognition returns nothing**  
→ Requires internet for Google Speech API  
→ Speak clearly, ensure `silence_threshold` is not too high

**MediaPipe not detecting face**  
→ Ensure good lighting; face the camera directly

**PDF not opening**  
→ Install a PDF viewer; on Linux: `sudo apt install evince`

---

## 🤝 Contributing

Pull requests welcome. Please:
1. Fork the repo
2. Create a feature branch
3. Write clean, commented code
4. Submit a PR with a description

---

## 📄 License

MIT License — free for personal and commercial use.

---

## 🙏 Acknowledgements

- [MediaPipe](https://mediapipe.dev/) — Face Mesh & iris landmark detection  
- [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) — Audio transcription  
- [ReportLab](https://www.reportlab.com/) — PDF generation  
- [Matplotlib](https://matplotlib.org/) — Analytics charts  

---

*Built as a portfolio-quality project demonstrating Computer Vision, NLP, Desktop GUI development, and Software Architecture.*
