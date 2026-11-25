"""Human-like conversation helpers for the avatar interviewer (pure functions, easy to test)."""
import random
import re

REACTIONS = {
    "high": ["That was a really strong answer.", "Excellent, you explained that very well.",
             "Great answer, thank you.", "Nice, that was clear and accurate."],
    "mid": ["Thanks, that covers the main idea.", "Okay, good effort.", "Alright, thank you for explaining that.",
            "Good, I can follow your thinking."],
    "low": ["Thanks for giving that a try.", "No worries, that one was a bit tricky.",
            "Okay, let's see how the next one goes.", "Thank you, we'll keep going."],
}
RETRY = ["Sorry, I didn't quite catch that. Could you please answer again?",
         "I couldn't hear you clearly. Could you say that once more?"]


def band(score: float) -> str:
    return "high" if score >= 75 else "mid" if score >= 45 else "low"


def first_sentence(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    out = m.group(1) if m else text
    return out[:limit].rstrip()


def reaction(score: float, feedback: str = "", use_feedback: bool = False, rnd=random) -> str:
    line = rnd.choice(REACTIONS[band(score)])
    if use_feedback and feedback:
        line += " " + first_sentence(feedback)
    return line


def greeting(name: str, avatar: str, skill: str, question: str) -> str:
    return (f"Hello {name}! I'm {avatar}, and I'll be your interviewer today for {skill}. "
            f"I'll ask a few questions, and you can answer naturally, just like a real conversation. "
            f"Let's begin. {question}")


def next_turn(reaction_text: str, question: str, q_no: int, total: int) -> str:
    lead = "Final question." if q_no == total else f"Question {q_no}."
    return f"{reaction_text} {lead} {question}"


def closing(reaction_text: str, name: str) -> str:
    return (f"{reaction_text} That was the final question. Thank you, {name}. "
            "Please click View my report to see your results and my feedback.")


def retry_prompt(question: str, rnd=random) -> str:
    return f"{rnd.choice(RETRY)} {question}"
