"""Database layer built on SQLAlchemy Core.

Default backend is a local SQLite file. Set DATABASE_URL to use PostgreSQL (or any SQLAlchemy URL).
All SQL here is kept portable (no dialect-specific functions).
"""
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

import config

_engine = None
TABLES = ["users", "interviews", "answers", "skill_proficiency", "recordings", "violations"]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------- connection
def get_engine():
    global _engine
    if _engine is None:
        url = config.DATABASE_URL
        kw = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False}
            if "///" in url:
                path = url.split("///", 1)[1]
                if path and path != ":memory:":
                    Path(path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, **kw)
    return _engine


def set_database_url(url: str) -> None:
    """Point the app at another database (used by tests / setup scripts)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    config.DATABASE_URL = url


def dialect() -> str:
    return get_engine().dialect.name


def safe_url(url: str | None = None) -> str:
    from sqlalchemy.engine import make_url
    return make_url(url or config.DATABASE_URL).render_as_string(hide_password=True)


def test_connection(url: str | None = None) -> tuple[bool, str, float]:
    """Try `SELECT 1`. Returns (ok, message, latency_ms)."""
    eng = None
    start = time.perf_counter()
    try:
        eng = get_engine() if url is None else create_engine(url, pool_pre_ping=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        ms = (time.perf_counter() - start) * 1000
        return True, f"Connected ({eng.dialect.name})", ms
    except ModuleNotFoundError as e:
        return False, f"Database driver missing: {e.name}. Install it (e.g. pip install psycopg2-binary).", 0.0
    except Exception as e:  # noqa: BLE001
        return False, str(e).splitlines()[0][:300], 0.0
    finally:
        if url is not None and eng is not None:
            eng.dispose()


@contextmanager
def conn():
    with get_engine().begin() as c:
        yield c


def _df(sql: str, **params) -> pd.DataFrame:
    with get_engine().connect() as c:
        return pd.read_sql_query(text(sql), c, params=params)


def _schema() -> list[str]:
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect() == "sqlite" else "SERIAL PRIMARY KEY"
    real = "DOUBLE PRECISION"
    return [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {pk}, username VARCHAR(64) UNIQUE NOT NULL, full_name VARCHAR(120), email VARCHAR(160),
            password_hash TEXT NOT NULL, salt VARCHAR(64) NOT NULL,
            role VARCHAR(16) NOT NULL DEFAULT 'candidate', is_active INTEGER NOT NULL DEFAULT 1,
            created_at VARCHAR(19) NOT NULL, last_login VARCHAR(19))""",
        f"""CREATE TABLE IF NOT EXISTS interviews (
            id {pk}, user_id INTEGER NOT NULL REFERENCES users(id), skill VARCHAR(120) NOT NULL,
            difficulty VARCHAR(20) NOT NULL, total_questions INTEGER NOT NULL,
            started_at VARCHAR(19) NOT NULL, finished_at VARCHAR(19), overall_score {real},
            summary TEXT, ai_mode VARCHAR(20) DEFAULT 'gemini',
            violations INTEGER DEFAULT 0, end_reason VARCHAR(30))""",
        f"""CREATE TABLE IF NOT EXISTS answers (
            id {pk}, interview_id INTEGER NOT NULL REFERENCES interviews(id), q_no INTEGER NOT NULL,
            question TEXT NOT NULL, answer TEXT, input_mode VARCHAR(12) DEFAULT 'voice',
            accuracy {real}, depth {real}, clarity {real}, relevance {real}, overall {real},
            filler_count INTEGER DEFAULT 0, word_count INTEGER DEFAULT 0,
            feedback TEXT, strengths TEXT, improvements TEXT, created_at VARCHAR(19) NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS skill_proficiency (
            user_id INTEGER NOT NULL REFERENCES users(id), skill VARCHAR(120) NOT NULL,
            proficiency {real} NOT NULL, sessions INTEGER NOT NULL DEFAULT 0, updated_at VARCHAR(19) NOT NULL,
            PRIMARY KEY (user_id, skill))""",
        f"""CREATE TABLE IF NOT EXISTS recordings (
            id {pk}, interview_id INTEGER NOT NULL REFERENCES interviews(id), user_id INTEGER NOT NULL REFERENCES users(id),
            q_no INTEGER NOT NULL, question TEXT, transcript TEXT, video_path VARCHAR(300), audio_path VARCHAR(300),
            mime VARCHAR(60), duration_sec {real}, size_bytes INTEGER DEFAULT 0, created_at VARCHAR(19) NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS violations (
            id {pk}, interview_id INTEGER NOT NULL REFERENCES interviews(id), user_id INTEGER NOT NULL REFERENCES users(id),
            kind VARCHAR(30), detail VARCHAR(200), created_at VARCHAR(19) NOT NULL)""",
    ]


def _ensure_columns() -> None:
    """Upgrade databases created by older versions (adds the proctoring columns)."""
    from sqlalchemy import inspect
    cols = {c["name"] for c in inspect(get_engine()).get_columns("interviews")}
    with conn() as c:
        if "violations" not in cols:
            c.execute(text("ALTER TABLE interviews ADD COLUMN violations INTEGER DEFAULT 0"))
        if "end_reason" not in cols:
            c.execute(text("ALTER TABLE interviews ADD COLUMN end_reason VARCHAR(30)"))


def init_db() -> None:
    with conn() as c:
        for stmt in _schema():
            c.execute(text(stmt))
    _ensure_columns()


# ----------------------------------------------------------------------- users
def create_user_row(username, password_hash, salt, full_name="", email="", role="candidate") -> int:
    with conn() as c:
        return c.execute(
            text("""INSERT INTO users(username, full_name, email, password_hash, salt, role, is_active, created_at)
                    VALUES (:u,:f,:e,:h,:s,:r,1,:t) RETURNING id"""),
            dict(u=username, f=full_name, e=email, h=password_hash, s=salt, r=role, t=now())).scalar()


def _one(sql, **p):
    with get_engine().connect() as c:
        row = c.execute(text(sql), p).mappings().first()
        return dict(row) if row else None


def get_user(user_id):
    return _one("SELECT * FROM users WHERE id=:i", i=user_id)


def get_user_by_username(username):
    return _one("SELECT * FROM users WHERE username=:u", u=username.strip().lower())


def list_users() -> list[dict]:
    df = _df("SELECT * FROM users ORDER BY username")
    return df.to_dict("records")


def users_with_stats_df() -> pd.DataFrame:
    return _df("""SELECT u.id, u.username, u.full_name, u.email, u.role, u.is_active, u.created_at, u.last_login,
                  COUNT(i.id) AS sessions
                  FROM users u LEFT JOIN interviews i ON i.user_id = u.id AND i.finished_at IS NOT NULL
                  GROUP BY u.id, u.username, u.full_name, u.email, u.role, u.is_active, u.created_at, u.last_login
                  ORDER BY u.username""")


def touch_login(user_id) -> None:
    with conn() as c:
        c.execute(text("UPDATE users SET last_login=:t WHERE id=:i"), dict(t=now(), i=user_id))


def update_user(user_id, **fields) -> None:
    allowed = {"full_name", "email", "role", "is_active", "password_hash", "salt"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k}=:{k}" for k in sets)
    with conn() as c:
        c.execute(text(f"UPDATE users SET {clause} WHERE id=:_id"), {**sets, "_id": user_id})


def _remove_recording_files(rows) -> None:
    from core import storage
    for r in rows:
        for key in ("video_path", "audio_path"):
            try:
                storage.delete_media(r[key])
            except Exception:  # noqa: BLE001
                pass


def delete_user(user_id) -> None:
    with get_engine().connect() as c:
        rows = [dict(r) for r in c.execute(text("SELECT video_path, audio_path FROM recordings WHERE user_id=:u"),
                                           dict(u=user_id)).mappings()]
    _remove_recording_files(rows)
    with conn() as c:
        p = dict(u=user_id)
        c.execute(text("DELETE FROM recordings WHERE user_id=:u"), p)
        c.execute(text("DELETE FROM violations WHERE user_id=:u"), p)
        c.execute(text("DELETE FROM answers WHERE interview_id IN (SELECT id FROM interviews WHERE user_id=:u)"), p)
        c.execute(text("DELETE FROM interviews WHERE user_id=:u"), p)
        c.execute(text("DELETE FROM skill_proficiency WHERE user_id=:u"), p)
        c.execute(text("DELETE FROM users WHERE id=:u"), p)


def wipe_data(keep_admins: bool = True) -> None:
    from core import storage
    with conn() as c:
        for t in ("recordings", "violations", "answers", "interviews", "skill_proficiency"):
            c.execute(text(f"DELETE FROM {t}"))
        c.execute(text("DELETE FROM users WHERE role <> 'admin'" if keep_admins else "DELETE FROM users"))
    storage.wipe_all()


# ------------------------------------------------------------------ interviews
def create_interview(user_id, skill, difficulty, total_questions, ai_mode="gemini", started_at=None) -> int:
    with conn() as c:
        return c.execute(
            text("""INSERT INTO interviews(user_id, skill, difficulty, total_questions, started_at, ai_mode)
                    VALUES (:u,:s,:d,:n,:t,:m) RETURNING id"""),
            dict(u=user_id, s=skill, d=difficulty, n=total_questions, t=started_at or now(), m=ai_mode)).scalar()


def max_interview_id() -> int:
    return int(_one("SELECT COALESCE(MAX(id), 0) AS m FROM interviews")["m"])


def interview_exists(user_id, skill, started_at=None, overall_score=None, max_id=None) -> bool:
    """Duplicate check. Matches on start time, or on skill+score when dates were shifted on import."""
    if overall_score is not None:
        return _one("""SELECT id FROM interviews WHERE user_id=:u AND skill=:s AND ai_mode='sample'
                       AND ABS(overall_score - :o) < 0.001 AND id <= :m""",
                    u=user_id, s=skill, o=overall_score, m=max_id if max_id is not None else 10**12) is not None
    return _one("SELECT id FROM interviews WHERE user_id=:u AND skill=:s AND started_at=:t",
                u=user_id, s=skill, t=started_at) is not None


def save_answer(interview_id, q_no, question, answer, input_mode, scores: dict, overall,
                filler_count, word_count, feedback, strengths, improvements, created_at=None) -> None:
    with conn() as c:
        c.execute(
            text("""INSERT INTO answers(interview_id,q_no,question,answer,input_mode,accuracy,depth,clarity,
                    relevance,overall,filler_count,word_count,feedback,strengths,improvements,created_at)
                    VALUES (:iid,:q,:qt,:a,:m,:ac,:de,:cl,:re,:ov,:fc,:wc,:fb,:st,:im,:t)"""),
            dict(iid=interview_id, q=q_no, qt=question, a=answer, m=input_mode,
                 ac=scores.get("accuracy"), de=scores.get("depth"), cl=scores.get("clarity"),
                 re=scores.get("relevance"), ov=overall, fc=filler_count, wc=word_count, fb=feedback,
                 st="\n".join(strengths), im="\n".join(improvements), t=created_at or now()))


def finish_interview(interview_id, overall_score, summary, finished_at=None, end_reason="completed",
                     violations=0) -> None:
    with conn() as c:
        c.execute(text("""UPDATE interviews SET finished_at=:f, overall_score=:o, summary=:s, end_reason=:r,
                          violations=:v WHERE id=:i"""),
                  dict(f=finished_at or now(), o=overall_score, s=summary, r=end_reason, v=violations, i=interview_id))


# ------------------------------------------------------------------ proficiency
def get_proficiency(user_id, skill):
    return _one("SELECT * FROM skill_proficiency WHERE user_id=:u AND skill=:s", u=user_id, s=skill)


def upsert_proficiency(user_id, skill, proficiency, sessions, updated_at=None) -> None:
    p = dict(u=user_id, s=skill, p=proficiency, n=sessions, t=updated_at or now())
    with conn() as c:
        updated = c.execute(text("""UPDATE skill_proficiency SET proficiency=:p, sessions=:n, updated_at=:t
                                    WHERE user_id=:u AND skill=:s"""), p).rowcount
        if not updated:
            c.execute(text("""INSERT INTO skill_proficiency(user_id, skill, proficiency, sessions, updated_at)
                              VALUES (:u,:s,:p,:n,:t)"""), p)


# ---------------------------------------------------------------------- queries
def get_interviews_df(user_id) -> pd.DataFrame:
    df = _df("""SELECT * FROM interviews WHERE user_id=:u AND finished_at IS NOT NULL
                AND COALESCE(end_reason, '') <> 'violations' ORDER BY started_at""", u=user_id)
    df["started_at"] = pd.to_datetime(df["started_at"])
    return df


def get_answers_df(user_id) -> pd.DataFrame:
    df = _df("""SELECT a.*, i.skill, i.difficulty, i.started_at FROM answers a
                JOIN interviews i ON i.id = a.interview_id
                WHERE i.user_id=:u AND i.finished_at IS NOT NULL AND COALESCE(i.end_reason, '') <> 'violations'
                ORDER BY a.created_at""", u=user_id)
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def get_proficiency_df(user_id) -> pd.DataFrame:
    return _df("SELECT skill, proficiency, sessions, updated_at FROM skill_proficiency WHERE user_id=:u", u=user_id)


def get_all_interviews_df() -> pd.DataFrame:
    df = _df("""SELECT i.*, u.username, u.full_name FROM interviews i JOIN users u ON u.id = i.user_id
                WHERE i.finished_at IS NOT NULL AND COALESCE(i.end_reason, '') <> 'violations' ORDER BY i.started_at""")
    df["started_at"] = pd.to_datetime(df["started_at"])
    return df


def get_all_answers_df() -> pd.DataFrame:
    return _df("""SELECT a.*, i.skill, u.username FROM answers a
                  JOIN interviews i ON i.id = a.interview_id JOIN users u ON u.id = i.user_id
                  WHERE i.finished_at IS NOT NULL AND COALESCE(i.end_reason, '') <> 'violations'""")


def get_all_proficiency_df() -> pd.DataFrame:
    return _df("""SELECT p.user_id, u.username, u.full_name, p.skill, p.proficiency, p.sessions
                  FROM skill_proficiency p JOIN users u ON u.id = p.user_id""")


def leaderboard_df() -> pd.DataFrame:
    df = _df("""SELECT u.id AS user_id, u.username, u.full_name, COUNT(i.id) AS sessions,
                AVG(i.overall_score) AS avg_score, MAX(i.overall_score) AS best_score
                FROM users u JOIN interviews i ON i.user_id = u.id
                WHERE i.finished_at IS NOT NULL AND COALESCE(i.end_reason, '') <> 'violations'
                GROUP BY u.id, u.username, u.full_name""")
    if df.empty:
        return df
    df["avg_score"] = df["avg_score"].round(1)
    df["best_score"] = df["best_score"].round(1)
    df = df.sort_values(["avg_score", "sessions"], ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    df["display"] = df.apply(lambda r: r["full_name"] or r["username"], axis=1)
    return df


def table_counts() -> dict:
    out = {}
    with get_engine().connect() as c:
        for t in TABLES:
            out[t] = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    return out


def sqlite_file() -> Path | None:
    if dialect() != "sqlite":
        return None
    path = get_engine().url.database
    return Path(path) if path and path != ":memory:" else None


# ------------------------------------------------------------------- recordings
def save_recording(interview_id, user_id, q_no, question, transcript, video_path, audio_path, mime,
                   duration_sec, size_bytes) -> int:
    with conn() as c:
        return c.execute(
            text("""INSERT INTO recordings(interview_id, user_id, q_no, question, transcript, video_path, audio_path,
                    mime, duration_sec, size_bytes, created_at)
                    VALUES (:i,:u,:q,:qt,:t,:v,:a,:m,:d,:s,:c) RETURNING id"""),
            dict(i=interview_id, u=user_id, q=q_no, qt=question, t=transcript, v=video_path, a=audio_path,
                 m=mime, d=duration_sec, s=size_bytes, c=now())).scalar()


def get_recording(recording_id):
    return _one("SELECT * FROM recordings WHERE id=:i", i=recording_id)


def get_recordings_for_interview(interview_id) -> dict:
    """{q_no: recording row} for one interview (latest per question)."""
    df = _df("SELECT * FROM recordings WHERE interview_id=:i ORDER BY id", i=interview_id)
    return {int(r["q_no"]): r for r in df.to_dict("records")}


def recordings_df() -> pd.DataFrame:
    """All recordings with owner, skill and answer score (admin review list)."""
    return _df("""SELECT r.id, r.interview_id, r.user_id, u.username, u.full_name, i.skill, r.q_no, r.question,
                  r.transcript, r.video_path, r.audio_path, r.mime, r.duration_sec, r.size_bytes, r.created_at,
                  a.overall AS score
                  FROM recordings r JOIN users u ON u.id = r.user_id JOIN interviews i ON i.id = r.interview_id
                  LEFT JOIN answers a ON a.interview_id = r.interview_id AND a.q_no = r.q_no
                  ORDER BY r.created_at DESC""")


def delete_recordings(ids) -> int:
    n = 0
    for rid in ids:
        row = get_recording(int(rid))
        if not row:
            continue
        _remove_recording_files([row])
        with conn() as c:
            c.execute(text("DELETE FROM recordings WHERE id=:i"), dict(i=int(rid)))
        n += 1
    return n


# ------------------------------------------------------------------- violations
def add_violation(interview_id, user_id, kind, detail) -> None:
    with conn() as c:
        c.execute(text("""INSERT INTO violations(interview_id, user_id, kind, detail, created_at)
                          VALUES (:i,:u,:k,:d,:t)"""),
                  dict(i=interview_id, u=user_id, k=(kind or "")[:30], d=(detail or "")[:200], t=now()))


def set_violation_count(interview_id, n) -> None:
    with conn() as c:
        c.execute(text("UPDATE interviews SET violations=:n WHERE id=:i"), dict(n=n, i=interview_id))


def violations_df() -> pd.DataFrame:
    """Every recorded violation with the candidate, skill and how the interview ended (admin view)."""
    return _df("""SELECT v.id, v.created_at, u.username, u.full_name, i.skill, v.interview_id, v.kind, v.detail,
                  i.violations AS interview_violations, i.end_reason
                  FROM violations v JOIN users u ON u.id = v.user_id JOIN interviews i ON i.id = v.interview_id
                  ORDER BY v.created_at DESC""")


def get_terminated_df(user_id) -> pd.DataFrame:
    return _df("""SELECT id, started_at, skill, difficulty, violations, summary FROM interviews
                  WHERE user_id=:u AND end_reason='violations' ORDER BY started_at DESC""", u=user_id)
