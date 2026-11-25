"""Skill scoring logic: weighted rubric, levels, proficiency tracking, speech metrics."""
import re
from typing import Iterable

import config


def clamp(x, lo=0.0, hi=10.0) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return lo


def compute_overall(scores: dict) -> float:
    """Weighted rubric (each criterion 0-10) -> 0-100 score."""
    total = sum(clamp(scores.get(k, 0)) * w for k, w in config.SCORE_WEIGHTS.items())
    return round(total * 10, 1)


def level_for(score: float) -> str:
    for threshold, name in config.LEVEL_BANDS:
        if score >= threshold:
            return name
    return "Beginner"


def interview_score(answer_overalls: Iterable[float]) -> float:
    vals = list(answer_overalls)
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def update_proficiency(old, new_score: float, alpha: float = config.PROFICIENCY_ALPHA) -> float:
    """Exponential moving average; first session sets the baseline."""
    if old is None:
        return round(new_score, 1)
    return round((1 - alpha) * old + alpha * new_score, 1)


def filler_stats(text: str) -> tuple[int, int]:
    """Return (filler_count, word_count)."""
    lowered = " " + re.sub(r"[^\w\s']", " ", text.lower()) + " "
    words = len(lowered.split())
    count = 0
    for f in config.FILLER_WORDS:
        count += len(re.findall(rf"\s{re.escape(f)}(?=\s)", lowered))
    return count, words


def adaptive_hint(last_overall) -> str:
    """Tell the question generator how to adjust difficulty."""
    if last_overall is None:
        return "same"
    if last_overall >= 80:
        return "harder"
    if last_overall < 40:
        return "easier"
    return "same"
