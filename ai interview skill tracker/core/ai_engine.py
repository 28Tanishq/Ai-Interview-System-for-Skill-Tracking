"""Generative-AI engine: dynamic question generation, answer evaluation, final feedback.

Primary backend : Google Gemini API (free tier, key from https://aistudio.google.com/apikey)
Fallback backend: offline question bank + keyword-coverage scoring (works with NO key/internet),
                  so the app never crashes if the API is missing, rate limited, or offline.
"""
import json
import random
import re

import config
from core import scoring

try:  # optional import so the app still runs without the SDK
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


def _extract_json(text: str) -> dict:
    """Parse JSON even if the model wrapped it in markdown fences."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


class AIEngine:
    def __init__(self, api_key: str = config.GEMINI_API_KEY, model: str = config.GEMINI_MODEL):
        self.model = model
        self.client = None
        self.last_error = None
        self.bank = config.load_question_bank()
        if api_key and genai is not None:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception as e:  # pragma: no cover
                self.last_error = str(e)

    # ------------------------------------------------------------------ helpers
    @property
    def online(self) -> bool:
        return self.client is not None

    @property
    def mode(self) -> str:
        return "gemini" if self.online else "offline"

    def _ask_json(self, prompt: str, temperature: float = 0.7) -> dict:
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        return _extract_json(resp.text)

    # --------------------------------------------------------- question generation
    def generate_question(self, skill: str, difficulty: str, q_no: int, total: int,
                          asked: list[str], last_overall=None) -> dict:
        """Return {'question', 'expected_topics', 'source'}."""
        hint = scoring.adaptive_hint(last_overall)
        if self.online:
            prompt = f"""You are a senior technical interviewer conducting a SPOKEN interview.
Skill under assessment: {skill}
Base difficulty: {difficulty}
This is question {q_no} of {total}.
Adaptive instruction: make this question {hint} than the previous one (same = keep similar level).
Questions already asked (do NOT repeat or paraphrase): {json.dumps(asked)}

Rules: one clear question that can be answered aloud in 30-90 seconds; no code-writing tasks;
conceptual or scenario based; do not include the answer.
Return ONLY JSON: {{"question": "...", "expected_topics": ["key point 1", "key point 2", "key point 3"]}}"""
            try:
                data = self._ask_json(prompt, temperature=0.9)
                q = str(data["question"]).strip()
                if q:
                    return {"question": q, "expected_topics": list(data.get("expected_topics", [])),
                            "source": "gemini"}
            except Exception as e:
                self.last_error = f"Gemini question generation failed: {e}"
        return self._offline_question(skill, difficulty, asked)

    def _offline_question(self, skill, difficulty, asked) -> dict:
        pool = self.bank.get(skill) or [q for qs in self.bank.values() for q in qs]
        fresh = [q for q in pool if q["question"] not in asked]
        preferred = [q for q in fresh if q["difficulty"] == difficulty] or fresh or pool
        q = random.choice(preferred)
        return {"question": q["question"], "expected_topics": q.get("keywords", []), "source": "offline"}

    # ------------------------------------------------------------ answer evaluation
    def evaluate_answer(self, skill: str, difficulty: str, question: str, answer: str,
                        expected_topics: list[str]) -> dict:
        """Return rubric dict: accuracy/depth/clarity/relevance (0-10) + feedback lists."""
        answer = (answer or "").strip()
        if not answer:
            return self._empty_eval()
        if self.online:
            prompt = f"""You are a fair, encouraging but rigorous technical interviewer.
Skill: {skill} | Level: {difficulty}
Question: {question}
Key points a strong answer covers: {json.dumps(expected_topics)}
Candidate's spoken answer (transcribed from speech; ignore minor transcription errors): \"\"\"{answer}\"\"\"

Score each criterion from 0 to 10 (integers or one decimal):
- accuracy: technical correctness
- depth: completeness, detail, examples
- clarity: structure and ease of understanding
- relevance: directly addresses the question
Return ONLY JSON:
{{"accuracy": 0, "depth": 0, "clarity": 0, "relevance": 0,
 "feedback": "2-3 sentence constructive feedback addressed to the candidate",
 "strengths": ["..."], "improvements": ["..."],
 "ideal_answer_hint": "1-2 sentences describing what a model answer includes"}}"""
            try:
                d = self._ask_json(prompt, temperature=0.2)
                return self._normalize_eval(d)
            except Exception as e:
                self.last_error = f"Gemini evaluation failed: {e}"
        return self._offline_eval(answer, expected_topics)

    def _normalize_eval(self, d: dict) -> dict:
        out = {k: scoring.clamp(d.get(k, 0)) for k in config.SCORE_WEIGHTS}
        out["feedback"] = str(d.get("feedback", "")).strip()
        out["strengths"] = [str(s) for s in d.get("strengths", [])][:4]
        out["improvements"] = [str(s) for s in d.get("improvements", [])][:4]
        out["ideal_answer_hint"] = str(d.get("ideal_answer_hint", "")).strip()
        out["source"] = "gemini"
        return out

    @staticmethod
    def _empty_eval() -> dict:
        return {"accuracy": 0, "depth": 0, "clarity": 0, "relevance": 0,
                "feedback": "No answer was provided for this question.",
                "strengths": [], "improvements": ["Attempt every question, even a partial answer earns credit."],
                "ideal_answer_hint": "", "source": "none"}

    @staticmethod
    def _offline_eval(answer: str, topics: list[str]) -> dict:
        low = answer.lower()
        hits = [t for t in topics if t.lower() in low]
        missed = [t for t in topics if t.lower() not in low]
        coverage = len(hits) / len(topics) if topics else 0.5
        words = len(answer.split())
        depth = min(10, words / 12)  # ~120 words -> full marks
        sentences = max(1, len(re.findall(r"[.!?]", answer)))
        clarity = 4 + min(5, sentences / 2) if words > 10 else 2
        return {
            "accuracy": round(coverage * 10, 1),
            "depth": round(min(10, depth * 0.5 + coverage * 5), 1),
            "clarity": round(min(10, clarity), 1),
            "relevance": round(min(10, 3 + coverage * 7), 1),
            "feedback": (f"Offline keyword evaluation: you covered {len(hits)} of {len(topics)} key concepts. "
                         "Add a Gemini API key for richer, context-aware feedback."),
            "strengths": [f"Mentioned: {', '.join(hits)}"] if hits else [],
            "improvements": [f"Consider covering: {', '.join(missed[:4])}"] if missed else [],
            "ideal_answer_hint": "", "source": "offline",
        }

    # ------------------------------------------------------------------ summary
    def final_summary(self, skill: str, difficulty: str, overall: float, qa_list: list[dict]) -> dict:
        """Return {'summary', 'top_strengths', 'focus_areas', 'resources'}."""
        if self.online:
            compact = [{"q": x["question"], "score": x["overall"], "improve": x.get("improvements", [])}
                       for x in qa_list]
            prompt = f"""You are a career coach reviewing a mock interview.
Skill: {skill} ({difficulty}). Overall score: {overall}/100 ({scoring.level_for(overall)}).
Per-question results: {json.dumps(compact)}
Return ONLY JSON: {{"summary": "3-4 sentence overall assessment", "top_strengths": ["..",".."],
"focus_areas": ["..",".."], "resources": ["specific topic or free resource to study", ".."]}}"""
            try:
                d = self._ask_json(prompt, temperature=0.4)
                return {"summary": str(d.get("summary", "")), "top_strengths": list(d.get("top_strengths", [])),
                        "focus_areas": list(d.get("focus_areas", [])), "resources": list(d.get("resources", []))}
            except Exception as e:
                self.last_error = f"Gemini summary failed: {e}"
        weak = [x["question"] for x in sorted(qa_list, key=lambda r: r["overall"])[:2]]
        return {
            "summary": f"You scored {overall}/100 in {skill}, which is {scoring.level_for(overall)} level. "
                       "Review the questions below where your score was lowest.",
            "top_strengths": [x["question"] for x in sorted(qa_list, key=lambda r: -r["overall"])[:1]],
            "focus_areas": weak,
            "resources": [f"Official {skill} documentation", "freeCodeCamp / Khan Academy practice material"],
        }
