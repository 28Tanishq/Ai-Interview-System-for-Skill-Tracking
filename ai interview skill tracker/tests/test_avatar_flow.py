"""End-to-end: simulate the browser component answering each turn, then check DB, files and admin playback."""
import base64
import shutil
import subprocess

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import config
from core import auth, dataset
from core import database as db
from core import storage

ROOT = str(config.BASE_DIR)
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed to build a sample recording")


@pytest.fixture()
def env(tmp_path, monkeypatch, fresh_db):
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "rec")
    vid = tmp_path / "sample.webm"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-f", "lavfi",
                    "-i", "sine=frequency=440", "-t", "1", "-c:v", "libvpx", "-c:a", "libopus", str(vid)],
                   check=True, capture_output=True)
    aud = tmp_path / "sample_a.webm"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1", "-c:a", "libopus", str(aud)],
                   check=True, capture_output=True)
    return base64.b64encode(vid.read_bytes()).decode(), base64.b64encode(aud.read_bytes()).decode()


def fake_room_factory(transcripts, v64, a64):
    """Behaves like the real component: returns one value per recorded turn, then keeps returning the last one."""
    import streamlit as st

    def fake(say, say_id, record, **kw):
        S = st.session_state
        S.setdefault("_said", []).append(say)
        if record and say_id not in S.setdefault("_answered", []):
            S["_answered"].append(say_id)
            text = transcripts[min(len(S["_answered"]) - 1, len(transcripts) - 1)]
            S["_last"] = {"type": "answer", "id": say_id, "transcript": text, "duration": 7.5, "reason": "silence",
                          "video_b64": v64 if text else "", "audio_b64": a64 if text else "",
                          "v_mime": "video/webm", "a_mime": "audio/webm"}
        return S.get("_last")
    return fake


def fake_proctor_factory(n_events):
    """Pretends the browser reported `n_events` window violations, one per script run (like real life)."""
    import streamlit as st

    def fake(violations, limit, enabled=True, key="proctor"):
        S = st.session_state
        done = S.setdefault("_pv", 0)
        if done < n_events:
            S["_pv"] = done + 1
            S["_pval"] = {"type": "violation", "id": f"t{done + 1}", "kind": "tab_hidden", "detail": "test", "n": done + 1}
        return S.get("_pval")
    return fake


def start_avatar_interview(user, fake_room, total=3, proctor_events=0):
    import core.avatar_room as ar
    import core.proctor as pr
    ar.interview_room = fake_room
    pr.proctor_monitor = fake_proctor_factory(proctor_events)
    at = AppTest.from_file(f"{ROOT}/app.py", default_timeout=120)
    at.session_state["auth_user"] = user
    at.run()
    for c in at.checkbox:                                   # rules + recording consent
        c.check()
    at.run()
    at.slider[0].set_value(total).run()
    [b for b in at.button if "Start" in b.label][0].click().run()
    return at


def test_full_avatar_interview_saves_recordings(env):
    dataset.load_sample()
    user = auth.authenticate("alice", config.DEMO_PASSWORD)[0]
    before = len(db.recordings_df())
    answer = "A list is mutable while a tuple is immutable, ordered, hashable and usable as a dictionary key."
    at = start_avatar_interview(user, fake_room_factory([answer], *env), total=3)
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["closing"] is True
    said = at.session_state["_said"]
    assert said[0].startswith("Hello Alice!") and any("Final question." in s for s in said)
    assert any("final question. Thank you, Alice" in s for s in said)

    recs = db.recordings_df()
    assert len(recs) - before == 3
    mine = recs[recs["username"] == "alice"].sort_values("id").tail(3)
    for _, r in mine.iterrows():
        assert storage.read_media(r["video_path"]) and storage.read_media(r["audio_path"])
        assert r["transcript"] == answer and r["score"] is not None

    [b for b in at.button if "View my report" in b.label][0].click().run()
    assert at.session_state["stage"] == "result" and not at.exception

    # admin can open the recordings tab and see them
    admin = AppTest.from_file(f"{ROOT}/pages/2_Admin.py", default_timeout=120)
    admin.session_state["auth_user"] = db.get_user_by_username(config.ADMIN_USERNAME)
    admin.run()
    assert not admin.exception, [e.value for e in admin.exception]
    assert any(m.label == "Recordings" and int(m.value) >= 3 for m in admin.metric)

    # a candidate cannot reach the admin page
    cand = AppTest.from_file(f"{ROOT}/pages/2_Admin.py", default_timeout=60)
    cand.session_state["auth_user"] = user
    cand.run()
    assert any("administrators only" in e.value for e in cand.error)


def test_unheard_answer_is_retried_then_skipped(env):
    dataset.load_sample()
    user = auth.authenticate("bob", config.DEMO_PASSWORD)[0]
    at = start_avatar_interview(user, fake_room_factory(["", "", "Stacks are LIFO and queues are FIFO."], *env), total=3)
    assert not at.exception, [e.value for e in at.exception]
    said = at.session_state["_said"]
    assert any(s.startswith(("Sorry, I didn't quite catch that", "I couldn't hear you clearly")) for s in said)
    skipped = db._df("SELECT * FROM answers WHERE input_mode='skipped'")
    assert len(skipped) == 1 and skipped.iloc[0]["overall"] == 0
    assert len(db._df("SELECT * FROM answers WHERE input_mode='video'")) == 2   # remaining two questions were heard
    assert len(db.recordings_df()) >= 1


def test_three_violations_end_the_interview_automatically(env):
    dataset.load_sample()
    user = auth.authenticate("carol", config.DEMO_PASSWORD)[0]
    prof_before = db.get_proficiency_df(user["id"]).set_index("skill")["proficiency"].to_dict()
    at = start_avatar_interview(user, lambda say, say_id, record, **kw: None, proctor_events=3)
    assert at.session_state["stage"] == "interview" and at.session_state["violations"] == 1   # 1st: warning only
    at.run()                                                                                 # 2nd violation arrives
    assert at.session_state["stage"] == "interview" and at.session_state["violations"] == 2
    at.run()                                                                                 # 3rd violation: auto end
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["stage"] == "result"
    assert at.session_state["summary"]["terminated"] is True and at.session_state["violations"] == 3
    assert any("Interview ended" in m.value for m in at.markdown)

    last = db._df("SELECT * FROM interviews ORDER BY id DESC LIMIT 1").iloc[0]
    assert last["end_reason"] == "violations" and last["violations"] == 3 and pd.isna(last["overall_score"])
    assert len(db.violations_df()) == 3
    # not counted anywhere: proficiency unchanged, not in analytics or leaderboard
    assert db.get_proficiency_df(user["id"]).set_index("skill")["proficiency"].to_dict() == prof_before
    assert int(last["id"]) not in db.get_interviews_df(user["id"])["id"].tolist()
    assert len(db.get_terminated_df(user["id"])) == 1

    admin = AppTest.from_file(f"{ROOT}/pages/2_Admin.py", default_timeout=120)
    admin.session_state["auth_user"] = db.get_user_by_username(config.ADMIN_USERNAME)
    admin.run()
    assert not admin.exception, [e.value for e in admin.exception]
    assert any(m.label == "Interviews auto-ended" and m.value == "1" for m in admin.metric)


def test_two_violations_only_warn(env):
    dataset.load_sample()
    user = auth.authenticate("dave", config.DEMO_PASSWORD)[0]
    at = start_avatar_interview(user, lambda say, say_id, record, **kw: None, proctor_events=2)
    at.run()                                                                                 # second violation arrives
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["stage"] == "interview" and at.session_state["violations"] == 2
    assert any("2 window violation" in e.value for e in at.error)
    assert any("Violations 2/3" in m.value for m in at.markdown)
    assert len(db.violations_df()) == 2
