import sqlite3

from streamlit.testing.v1 import AppTest

import config
from core import auth
from core import database as db

ROOT = str(config.BASE_DIR)


def test_old_database_is_upgraded(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)       # a v3-style database without the proctoring columns
    con.executescript("""
    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, full_name TEXT, email TEXT,
        password_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'candidate', is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL, last_login TEXT);
    CREATE TABLE interviews (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, skill TEXT NOT NULL,
        difficulty TEXT NOT NULL, total_questions INTEGER NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
        overall_score REAL, summary TEXT, ai_mode TEXT DEFAULT 'gemini');
    INSERT INTO users(username,password_hash,salt,created_at) VALUES ('old','x','y','2026-01-01 00:00:00');
    INSERT INTO interviews(user_id,skill,difficulty,total_questions,started_at,finished_at,overall_score)
        VALUES (1,'SQL','Beginner',3,'2026-01-01 10:00:00','2026-01-01 10:10:00',70);
    """)
    con.commit()
    con.close()
    db.set_database_url(f"sqlite:///{path.as_posix()}")
    db.init_db()                                   # must add columns without losing data
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(interviews)")}
    assert {"violations", "end_reason"} <= cols
    assert len(db.get_interviews_df(1)) == 1       # old row still visible (NULL end_reason counts as completed)
    db.add_violation(1, 1, "tab_hidden", "x")
    assert len(db.violations_df()) == 1
    db.set_database_url("sqlite:///:memory:")


def test_theme_toggle_switches_css(fresh_db):
    at = AppTest.from_file(f"{ROOT}/app.py", default_timeout=60).run()        # login page has the toggle
    assert not at.exception and len(at.toggle) == 1
    assert any(config.BASE_DIR and "#f4f6fb" in m.value for m in at.markdown)   # light background token
    at.toggle[0].set_value(True).run()
    assert at.session_state["dark_mode"] is True
    html = " ".join(m.value for m in at.markdown)
    assert "#0e1120" in html and "color-scheme:dark" in html


def test_theme_survives_logout(fresh_db):
    user = auth.authenticate(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)[0]
    at = AppTest.from_file(f"{ROOT}/app.py", default_timeout=60)
    at.session_state["auth_user"] = user
    at.session_state["dark_mode"] = True
    at.run()
    assert not at.exception
    [b for b in at.button if "Log out" in b.label][0].click().run()
    assert "auth_user" not in at.session_state and at.session_state["dark_mode"] is True


def test_dashboard_and_admin_render_in_dark_mode(fresh_db):
    from core import dataset
    dataset.load_sample()
    admin = db.get_user_by_username(config.ADMIN_USERNAME)
    for page in ("pages/1_Dashboard.py", "pages/2_Admin.py"):
        at = AppTest.from_file(f"{ROOT}/{page}", default_timeout=120)
        at.session_state["auth_user"] = admin
        at.session_state["dark_mode"] = True
        at.run()
        assert not at.exception, (page, [e.value for e in at.exception])
