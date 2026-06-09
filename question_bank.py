"""
question_bank.py
----------------
Curated interview question bank with categories, difficulty levels,
and STAR-method tips. Used by the Interview Session page to prompt
the candidate with real questions during practice.
"""

import random
from typing import List, Dict, Optional


QUESTIONS: List[Dict] = [
    # ── Behavioural ──────────────────────────────────────────────────────────
    {
        "id": 1, "category": "Behavioural", "difficulty": "Easy",
        "question": "Tell me about yourself.",
        "tip": "Use the Present-Past-Future framework: current role → relevant background → why this opportunity.",
        "keywords": ["background", "experience", "role"],
    },
    {
        "id": 2, "category": "Behavioural", "difficulty": "Medium",
        "question": "Describe a time you handled a difficult colleague or conflict at work.",
        "tip": "STAR: Situation → Task → Action → Result. Focus on your actions, not blame.",
        "keywords": ["conflict", "team", "resolution"],
    },
    {
        "id": 3, "category": "Behavioural", "difficulty": "Medium",
        "question": "Give an example of a goal you set and how you achieved it.",
        "tip": "Be specific with numbers: timeline, metrics, outcome.",
        "keywords": ["goal", "achievement", "result"],
    },
    {
        "id": 4, "category": "Behavioural", "difficulty": "Hard",
        "question": "Tell me about a time you failed. What did you learn?",
        "tip": "Own the failure, describe concrete learning, show what changed.",
        "keywords": ["failure", "learning", "growth"],
    },
    {
        "id": 5, "category": "Behavioural", "difficulty": "Medium",
        "question": "Describe a situation where you had to adapt quickly to change.",
        "tip": "Emphasise flexibility, speed of learning, and positive outcome.",
        "keywords": ["change", "adapt", "flexibility"],
    },
    {
        "id": 6, "category": "Behavioural", "difficulty": "Easy",
        "question": "What is your greatest professional achievement?",
        "tip": "Quantify impact wherever possible — revenue, time saved, users served.",
        "keywords": ["achievement", "proud", "impact"],
    },
    {
        "id": 7, "category": "Behavioural", "difficulty": "Medium",
        "question": "Tell me about a time you led a team through a challenging project.",
        "tip": "Highlight leadership style, how you motivated others, and measurable outcome.",
        "keywords": ["leadership", "team", "project"],
    },
    {
        "id": 8, "category": "Behavioural", "difficulty": "Hard",
        "question": "Describe a time you disagreed with your manager. How did you handle it?",
        "tip": "Show respect, data-driven reasoning, and willingness to align after discussion.",
        "keywords": ["disagree", "manager", "professional"],
    },

    # ── Situational ───────────────────────────────────────────────────────────
    {
        "id": 9, "category": "Situational", "difficulty": "Medium",
        "question": "You have three urgent deadlines at the same time. How do you prioritise?",
        "tip": "Discuss impact vs urgency matrix; communicate proactively with stakeholders.",
        "keywords": ["prioritise", "deadline", "pressure"],
    },
    {
        "id": 10, "category": "Situational", "difficulty": "Hard",
        "question": "A key team member quits the day before a critical delivery. What do you do?",
        "tip": "Show crisis management: assess gap, redistribute, communicate risk, deliver.",
        "keywords": ["crisis", "delivery", "team"],
    },
    {
        "id": 11, "category": "Situational", "difficulty": "Medium",
        "question": "You discover a serious bug in production 30 minutes before a big demo. What do you do?",
        "tip": "Triage severity, inform stakeholders early, propose workaround, stay calm.",
        "keywords": ["bug", "production", "pressure"],
    },
    {
        "id": 12, "category": "Situational", "difficulty": "Easy",
        "question": "A client is unhappy with the work you delivered. How do you respond?",
        "tip": "Listen first, empathise, own any gaps, present a clear remediation plan.",
        "keywords": ["client", "feedback", "resolution"],
    },

    # ── Competency ────────────────────────────────────────────────────────────
    {
        "id": 13, "category": "Competency", "difficulty": "Easy",
        "question": "What are your three greatest strengths?",
        "tip": "Choose strengths relevant to the role and back each with a micro-example.",
        "keywords": ["strengths", "skills", "value"],
    },
    {
        "id": 14, "category": "Competency", "difficulty": "Medium",
        "question": "Where do you see yourself in five years?",
        "tip": "Align your growth trajectory with the company's direction. Show ambition + realism.",
        "keywords": ["future", "growth", "ambition"],
    },
    {
        "id": 15, "category": "Competency", "difficulty": "Medium",
        "question": "Why do you want to leave your current role?",
        "tip": "Stay positive. Focus on what you're moving toward, not what you're escaping.",
        "keywords": ["leaving", "motivation", "move"],
    },
    {
        "id": 16, "category": "Competency", "difficulty": "Easy",
        "question": "Why should we hire you over other candidates?",
        "tip": "Specific skills + proven track record + cultural fit = your unique value prop.",
        "keywords": ["hire", "unique", "value"],
    },
    {
        "id": 17, "category": "Competency", "difficulty": "Hard",
        "question": "Describe your approach to learning a completely new technology or domain quickly.",
        "tip": "Show structured learning: docs → small project → community → feedback loop.",
        "keywords": ["learning", "new", "technology"],
    },

    # ── Technical / General ───────────────────────────────────────────────────
    {
        "id": 18, "category": "Technical", "difficulty": "Medium",
        "question": "Walk me through how you would design a scalable REST API.",
        "tip": "Cover: versioning, auth, rate limiting, pagination, error handling, docs.",
        "keywords": ["api", "design", "scalable"],
    },
    {
        "id": 19, "category": "Technical", "difficulty": "Easy",
        "question": "Explain the difference between SQL and NoSQL databases and when you'd use each.",
        "tip": "SQL: ACID, structured, relations. NoSQL: flexible schema, horizontal scale.",
        "keywords": ["database", "sql", "nosql"],
    },
    {
        "id": 20, "category": "Technical", "difficulty": "Hard",
        "question": "How would you approach debugging a memory leak in a production service?",
        "tip": "Profiling → heap snapshots → identify growth patterns → targeted fix → monitor.",
        "keywords": ["debug", "memory", "production"],
    },

    # ── Culture / Motivation ──────────────────────────────────────────────────
    {
        "id": 21, "category": "Culture", "difficulty": "Easy",
        "question": "What type of work environment do you thrive in?",
        "tip": "Be honest but align with what you know of the company culture.",
        "keywords": ["environment", "culture", "thrive"],
    },
    {
        "id": 22, "category": "Culture", "difficulty": "Easy",
        "question": "How do you stay motivated during repetitive or low-stimulation tasks?",
        "tip": "Gamification, milestones, connecting to larger purpose — show self-awareness.",
        "keywords": ["motivation", "repetitive", "focus"],
    },
    {
        "id": 23, "category": "Culture", "difficulty": "Medium",
        "question": "How do you handle receiving critical feedback?",
        "tip": "Thank → understand → reflect → act. Show growth mindset with an example.",
        "keywords": ["feedback", "criticism", "growth"],
    },

    # ── Closing ───────────────────────────────────────────────────────────────
    {
        "id": 24, "category": "Closing", "difficulty": "Easy",
        "question": "Do you have any questions for us?",
        "tip": "Always ask 2–3 thoughtful questions: team structure, success metrics, growth paths.",
        "keywords": ["questions", "curiosity", "interest"],
    },
    {
        "id": 25, "category": "Closing", "difficulty": "Easy",
        "question": "What is your expected compensation range?",
        "tip": "Research market rate. Give a range anchored high. Tie to total comp, not just salary.",
        "keywords": ["salary", "compensation", "offer"],
    },
]

CATEGORIES  = sorted(set(q["category"] for q in QUESTIONS))
DIFFICULTIES = ["Easy", "Medium", "Hard"]


class QuestionBank:
    """
    Provides filtered, randomised access to the interview question bank.
    Tracks which questions have been shown in the current session to avoid
    repeats.
    """

    def __init__(self):
        self._all       = list(QUESTIONS)
        self._shown_ids = set()
        self._current:  Optional[Dict] = None

    # ─── Query API ────────────────────────────────────────────────────────────

    def get_random(
        self,
        category:   Optional[str] = None,
        difficulty: Optional[str] = None,
        avoid_repeats: bool = True,
    ) -> Optional[Dict]:
        """Return a random question matching the given filters."""
        pool = self._filter(category, difficulty)
        if avoid_repeats:
            pool = [q for q in pool if q["id"] not in self._shown_ids]
        if not pool:
            # Reset if exhausted
            self._shown_ids.clear()
            pool = self._filter(category, difficulty)
        if not pool:
            return None

        self._current = random.choice(pool)
        self._shown_ids.add(self._current["id"])
        return self._current

    def get_by_id(self, question_id: int) -> Optional[Dict]:
        for q in self._all:
            if q["id"] == question_id:
                return q
        return None

    def get_all(
        self,
        category:   Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> List[Dict]:
        return self._filter(category, difficulty)

    def get_categories(self) -> List[str]:
        return CATEGORIES

    def get_difficulties(self) -> List[str]:
        return DIFFICULTIES

    def reset_session(self):
        """Allow all questions to appear again."""
        self._shown_ids.clear()
        self._current = None

    @property
    def current_question(self) -> Optional[Dict]:
        return self._current

    # ─── Private ──────────────────────────────────────────────────────────────

    def _filter(
        self,
        category:   Optional[str],
        difficulty: Optional[str],
    ) -> List[Dict]:
        pool = self._all
        if category and category != "All":
            pool = [q for q in pool if q["category"] == category]
        if difficulty and difficulty != "All":
            pool = [q for q in pool if q["difficulty"] == difficulty]
        return pool
