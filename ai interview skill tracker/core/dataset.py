"""Import example / external datasets (CSV) into the database."""
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import config
from core import auth, scoring
from core import database as db

USER_COLS = ["username", "full_name", "email", "role"]
INTERVIEW_COLS = ["interview_id", "username", "skill", "difficulty", "total_questions", "started_at",
                  "finished_at", "overall_score", "summary", "ai_mode"]
ANSWER_COLS = ["interview_id", "q_no", "question", "answer", "input_mode", "accuracy", "depth", "clarity",
               "relevance", "overall", "filler_count", "word_count", "feedback", "strengths", "improvements",
               "created_at"]
FMT = "%Y-%m-%d %H:%M:%S"


def _check(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {', '.join(missing)}")


def read_sample_dir(directory: Path = config.SAMPLE_DIR):
    return (pd.read_csv(directory / "users.csv"), pd.read_csv(directory / "interviews.csv"),
            pd.read_csv(directory / "answers.csv"))


def import_dataset(users: pd.DataFrame, interviews: pd.DataFrame, answers: pd.DataFrame,
                   default_password: str = config.DEMO_PASSWORD, shift_dates: bool = True) -> dict:
    """Insert users, interviews, answers and rebuild proficiency. Safe to run twice (de-duplicates)."""
    _check(users, USER_COLS, "users.csv")
    _check(interviews, INTERVIEW_COLS, "interviews.csv")
    _check(answers, ANSWER_COLS, "answers.csv")
    interviews = interviews.copy()
    answers = answers.copy()

    # Move all dates so the newest session is yesterday: sample data always looks fresh.
    if shift_dates and not interviews.empty:
        newest = pd.to_datetime(interviews["finished_at"].fillna(interviews["started_at"])).max()
        delta = (datetime.now() - timedelta(days=1)) - newest.to_pydatetime()
        for df, cols in ((interviews, ["started_at", "finished_at"]), (answers, ["created_at"])):
            for col in cols:
                df[col] = (pd.to_datetime(df[col]) + delta).dt.strftime(FMT)

    counts = {"users": 0, "interviews": 0, "answers": 0, "skipped_interviews": 0}
    uid: dict[str, int] = {}
    pre_max = db.max_interview_id()  # only compare against rows that existed before this import
    for r in users.fillna("").to_dict("records"):
        name = str(r["username"]).strip().lower()
        existing = db.get_user_by_username(name)
        if existing:
            uid[name] = existing["id"]
            continue
        user, err = auth.create_user(name, default_password, r["full_name"], r["email"],
                                     r["role"] if r["role"] in ("candidate", "admin") else "candidate")
        if err:
            raise ValueError(f"Cannot create user '{name}': {err}")
        uid[name] = user["id"]
        counts["users"] += 1

    for r in interviews.sort_values("started_at").fillna("").to_dict("records"):
        user_id = uid.get(str(r["username"]).strip().lower())
        if user_id is None:
            continue
        if db.interview_exists(user_id, r["skill"], r["started_at"],
                               float(r["overall_score"]) if shift_dates and r["ai_mode"] == "sample" else None,
                               max_id=pre_max):
            counts["skipped_interviews"] += 1
            continue
        iid = db.create_interview(user_id, r["skill"], r["difficulty"], int(r["total_questions"]),
                                  r["ai_mode"] or "sample", r["started_at"])
        db.finish_interview(iid, float(r["overall_score"]), r["summary"], r["finished_at"] or r["started_at"])
        counts["interviews"] += 1
        for a in answers[answers["interview_id"] == r["interview_id"]].fillna("").to_dict("records"):
            rub = {k: float(a[k] or 0) for k in config.SCORE_WEIGHTS}
            db.save_answer(iid, int(a["q_no"]), a["question"], a["answer"], a["input_mode"] or "voice", rub,
                           float(a["overall"] or 0), int(a["filler_count"] or 0), int(a["word_count"] or 0),
                           a["feedback"], [s for s in str(a["strengths"]).split("\n") if s],
                           [s for s in str(a["improvements"]).split("\n") if s], a["created_at"])
            counts["answers"] += 1

    for user_id in uid.values():
        rebuild_proficiency(user_id)
    return counts


def rebuild_proficiency(user_id: int) -> None:
    """Recompute per-skill proficiency (EMA) from the user's completed interviews, oldest first."""
    df = db.get_interviews_df(user_id)
    for skill, grp in df.groupby("skill"):
        prof = None
        for score in grp.sort_values("started_at")["overall_score"]:
            prof = scoring.update_proficiency(prof, float(score))
        db.upsert_proficiency(user_id, skill, prof, len(grp), grp["started_at"].max().strftime(FMT))


def load_sample(shift_dates: bool = True) -> dict:
    return import_dataset(*read_sample_dir(), shift_dates=shift_dates)
