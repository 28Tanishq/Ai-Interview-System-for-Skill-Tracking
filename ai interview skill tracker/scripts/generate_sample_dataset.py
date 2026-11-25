"""Regenerate the example dataset in data/sample_dataset/ (users, interviews, answers CSVs).

Usage: python -m scripts.generate_sample_dataset
The CSVs are already shipped; run this only if you want fresh random data.
"""
import random
from datetime import datetime, timedelta

import pandas as pd

import config
from core import scoring

# username -> (full name, email, {skill: (starting score, gain per session)})
PROFILES = {
    "alice": ("Alice Johnson", "alice@example.com", {"Python": (58, 2.4), "Machine Learning": (50, 2.0), "SQL": (48, 1.2)}),
    "bob": ("Bob Martinez", "bob@example.com", {"SQL": (68, 1.5), "Data Structures & Algorithms": (52, 2.2), "Web Development": (45, 1.8)}),
    "carol": ("Carol Singh", "carol@example.com", {"Python": (28, 3.6), "Web Development": (32, 3.0)}),
    "dave": ("Dave Okafor", "dave@example.com", {"Machine Learning": (44, 0.8), "Data Structures & Algorithms": (40, 1.0), "Python": (50, 0.5)}),
    "eve": ("Eve Chen", "eve@example.com", {"Python": (76, 1.0), "Machine Learning": (72, 1.2), "Data Structures & Algorithms": (70, 1.4), "Web Development": (68, 1.1)}),
}
OPENERS = ["I would say it comes down to", "The main idea involves", "Basically, this is about", "To answer this I would cover"]
CLOSERS = ["I would also give a practical example from a project.", "That is the general idea.", "", "I can go deeper on any of these."]
FEEDBACK = {
    "high": "Excellent answer with accurate details and good structure. Adding a concrete production example would make it perfect.",
    "mid": "Solid understanding of the core idea. Some key points were missing; try to add specifics and edge cases.",
    "low": "You touched on the topic but missed several key concepts. Review the fundamentals and practise explaining them step by step.",
}


def band(x):
    return "high" if x >= 70 else "mid" if x >= 45 else "low"


def clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def build(seed: int = 7, days: int = 95):
    rnd = random.Random(seed)
    bank = config.load_question_bank()
    start = datetime(2026, 1, 5, 9, 0, 0)
    users, interviews, answers = [], [], []
    users.append(dict(username="admin", full_name="Administrator", email="admin@example.com", role="admin"))
    iid = 0
    for uname, (full, email, skills) in PROFILES.items():
        users.append(dict(username=uname, full_name=full, email=email, role="candidate"))
        n_sessions = rnd.randint(12, 16)
        counters = {s: 0 for s in skills}
        for n in range(n_sessions):
            skill = rnd.choice(list(skills))
            base, gain = skills[skill]
            score_target = clip(base + gain * counters[skill] + rnd.uniform(-6, 6))
            counters[skill] += 1
            when = start + timedelta(days=int(n * days / n_sessions) + rnd.randint(0, 2), hours=rnd.randint(0, 10),
                                     minutes=rnd.randint(0, 59))
            diff = config.DIFFICULTIES[0 if score_target < 45 else 1 if score_target < 70 else 2]
            qs = rnd.sample(bank[skill], 5)
            iid += 1
            overalls = []
            for q_no, q in enumerate(qs, 1):
                a_score = clip(score_target + rnd.uniform(-14, 14))
                rub = {k: round(clip(a_score / 10 + rnd.uniform(-1.2, 1.2), 0, 10), 1) for k in config.SCORE_WEIGHTS}
                ov = scoring.compute_overall(rub)
                overalls.append(ov)
                kws = q["keywords"]
                k = max(1, round(rub["accuracy"] / 10 * len(kws)))
                picked = rnd.sample(kws, min(k, len(kws)))
                parts = [rnd.choice(OPENERS) + " " + ", ".join(picked[:-1]) + (" and " if len(picked) > 1 else "") + picked[-1] + "."]
                if ov >= 55:
                    parts.append(f"In practice {picked[0]} matters because it affects how the system behaves at scale.")
                parts.append(rnd.choice(CLOSERS))
                text = " ".join(p for p in parts if p)
                if rnd.random() < max(0.15, 0.8 - n * 0.05):
                    text = text.replace("I would", "um, I would", 1).replace("Basically,", "basically, like,", 1)
                fillers, words = scoring.filler_stats(text)
                answers.append(dict(
                    interview_id=iid, q_no=q_no, question=q["question"], answer=text, input_mode="voice", **rub,
                    overall=ov, filler_count=fillers, word_count=words, feedback=FEEDBACK[band(ov)],
                    strengths=f"Mentioned {picked[0]}" if ov >= 40 else "",
                    improvements="Cover: " + ", ".join(rnd.sample(kws, min(2, len(kws)))) if ov < 85 else "",
                    created_at=(when + timedelta(minutes=q_no * 2)).strftime("%Y-%m-%d %H:%M:%S")))
            total = scoring.interview_score(overalls)
            interviews.append(dict(
                interview_id=iid, username=uname, skill=skill, difficulty=diff, total_questions=5,
                started_at=when.strftime("%Y-%m-%d %H:%M:%S"),
                finished_at=(when + timedelta(minutes=14)).strftime("%Y-%m-%d %H:%M:%S"), overall_score=total,
                summary=f"Scored {total}/100 in {skill} ({scoring.level_for(total)} level). " + FEEDBACK[band(total)],
                ai_mode="sample"))
    return pd.DataFrame(users), pd.DataFrame(interviews), pd.DataFrame(answers)


if __name__ == "__main__":
    u, i, a = build()
    config.SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    u.to_csv(config.SAMPLE_DIR / "users.csv", index=False)
    i.to_csv(config.SAMPLE_DIR / "interviews.csv", index=False)
    a.to_csv(config.SAMPLE_DIR / "answers.csv", index=False)
    print(f"Wrote {len(u)} users, {len(i)} interviews, {len(a)} answers to {config.SAMPLE_DIR}")
