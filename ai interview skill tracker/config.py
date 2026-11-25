"""Central configuration for the AI Interview Skill Tracker."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# ---- AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# ---- Database (any SQLAlchemy URL; SQLite file by default)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'skilltracker.db').as_posix()}").strip()

# ---- Accounts
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@123")
AUTO_LOAD_SAMPLE = _flag("AUTO_LOAD_SAMPLE", "1")
SHOW_DEMO_HINT = _flag("SHOW_DEMO_HINT", "1")
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 30

# ---- Proctoring (window violations)
PROCTORING_ENABLED = _flag("PROCTORING_ENABLED", "1")
MAX_VIOLATIONS = int(os.getenv("MAX_VIOLATIONS", "3"))            # interview ends automatically at this count
PROCTOR_GRACE_MS = int(os.getenv("PROCTOR_GRACE_MS", "6000"))     # ignore blur right after the page loads

# ---- Data files
QUESTION_BANK_PATH = BASE_DIR / "data" / "question_bank.json"
SAMPLE_DIR = BASE_DIR / "data" / "sample_dataset"

# ---- Recordings / avatar interview
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage" / "recordings"))
AVATAR_NAME = os.getenv("AVATAR_NAME", "Aria")
MAX_ANSWER_SECONDS = int(os.getenv("MAX_ANSWER_SECONDS", "120"))      # hard cap per answer
SILENCE_SECONDS = float(os.getenv("SILENCE_SECONDS", "3.5"))           # pause that ends an answer
NO_SPEECH_SECONDS = int(os.getenv("NO_SPEECH_SECONDS", "15"))          # give up if nobody speaks

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]

# Weights for the 4 rubric criteria (each scored 0-10 by the AI). Sum = 1.0
SCORE_WEIGHTS = {
    "accuracy": 0.40,   # technical correctness
    "depth": 0.25,      # completeness / detail / examples
    "clarity": 0.20,    # structure and communication
    "relevance": 0.15,  # answers the question asked
}

# Skill level bands (0-100 scale)
LEVEL_BANDS = [(80, "Expert"), (60, "Advanced"), (40, "Intermediate"), (0, "Beginner")]

# Weight of the newest interview in the running proficiency (exponential moving average)
PROFICIENCY_ALPHA = 0.35

FILLER_WORDS = ["um", "uh", "like", "you know", "basically", "actually", "sort of", "kind of", "i mean"]

SPEECH_LANGUAGES = {
    "English (US)": "en-US",
    "English (India)": "en-IN",
    "English (UK)": "en-GB",
    "Hindi": "hi-IN",
}

SKILL_EMOJI = {"Python": "🐍", "SQL": "🗄️", "Machine Learning": "🤖",
               "Data Structures & Algorithms": "🧮", "Web Development": "🌐"}


def load_question_bank() -> dict:
    with open(QUESTION_BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
