import config
from core import auth, dataset
from core import database as db
from core import scoring
from core.ai_engine import AIEngine, _extract_json


def test_overall_weights_sum():
    assert abs(sum(config.SCORE_WEIGHTS.values()) - 1.0) < 1e-9


def test_compute_overall_bounds():
    assert scoring.compute_overall({k: 10 for k in config.SCORE_WEIGHTS}) == 100.0
    assert scoring.compute_overall({k: 0 for k in config.SCORE_WEIGHTS}) == 0.0
    assert scoring.compute_overall({k: 99 for k in config.SCORE_WEIGHTS}) == 100.0


def test_levels_and_proficiency():
    assert [scoring.level_for(x) for x in (85, 65, 45, 10)] == ["Expert", "Advanced", "Intermediate", "Beginner"]
    assert scoring.update_proficiency(None, 70) == 70
    assert scoring.update_proficiency(50, 90, alpha=0.5) == 70


def test_filler_stats():
    fillers, words = scoring.filler_stats("Um, basically it is like a list, you know.")
    assert fillers >= 4 and words == 9


def test_json_extraction():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Here: {"a": 2} done') == {"a": 2}


def test_offline_engine_flow():
    eng = AIEngine(api_key="")
    assert not eng.online
    q = eng.generate_question("Python", "Beginner", 1, 3, [])
    ev = eng.evaluate_answer("Python", "Beginner", q["question"], " ".join(q["expected_topics"]) + " detail",
                             q["expected_topics"])
    assert ev["accuracy"] == 10
    assert eng.evaluate_answer("Python", "Beginner", q["question"], "", [])["accuracy"] == 0


def test_password_hashing():
    h, s = auth.hash_password("Secret123")
    assert auth.verify_password("Secret123", h, s) and not auth.verify_password("wrong", h, s)
    assert auth.validate_password("short1") and auth.validate_password("onlyletters")
    assert auth.validate_password("Good1234") is None


def test_register_login_roles(fresh_db):
    u, err = auth.create_user("Tester", "Passw0rd1", "Test User", "t@x.com")
    assert err is None and u["username"] == "tester" and u["role"] == "candidate"
    assert auth.create_user("tester", "Passw0rd1")[1] == "That username is already taken."
    assert auth.create_user("a", "Passw0rd1")[1]
    assert auth.authenticate("tester", "Passw0rd1")[0]["id"] == u["id"]
    assert auth.authenticate("tester", "nope")[1]
    db.update_user(u["id"], is_active=0)
    assert "deactivated" in auth.authenticate("tester", "Passw0rd1")[1]
    assert auth.authenticate(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)[0]["role"] == "admin"


def test_interview_roundtrip(fresh_db):
    u, _ = auth.create_user("bob", "Passw0rd1")
    iid = db.create_interview(u["id"], "SQL", "Beginner", 1)
    db.save_answer(iid, 1, "q?", "a", "typed", {"accuracy": 5, "depth": 5, "clarity": 5, "relevance": 5},
                   50, 0, 1, "ok", ["s"], ["i"])
    db.finish_interview(iid, 50, "sum")
    db.upsert_proficiency(u["id"], "SQL", 50, 1)
    db.upsert_proficiency(u["id"], "SQL", 60, 2)  # update path
    assert len(db.get_interviews_df(u["id"])) == 1
    assert len(db.get_answers_df(u["id"])) == 1
    assert db.get_proficiency(u["id"], "SQL")["proficiency"] == 60
    assert db.leaderboard_df().iloc[0]["username"] == "bob"
    db.delete_user(u["id"])
    assert db.get_user_by_username("bob") is None


def test_sample_dataset_import(fresh_db):
    res = dataset.load_sample()
    assert res["users"] == 5 and res["interviews"] == 69 and res["answers"] == 345
    again = dataset.load_sample()
    assert again["interviews"] == 0 and again["users"] == 0
    assert auth.authenticate("alice", config.DEMO_PASSWORD)[0]
    assert len(db.leaderboard_df()) == 5
    assert not db.get_all_proficiency_df().empty


def test_connection_helpers(fresh_db):
    ok, msg, _ = db.test_connection()
    assert ok and "sqlite" in msg
    assert db.test_connection("sqlite:///:memory:")[0]
    assert not db.test_connection("postgresql://u:p@127.0.0.1:1/none")[0]
    assert "***" in db.safe_url("postgresql://u:secret@h/db")
