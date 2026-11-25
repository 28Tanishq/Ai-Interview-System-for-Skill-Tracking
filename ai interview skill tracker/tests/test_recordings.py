import pytest

import config
from core import auth, conversation, recordings, storage
from core import database as db


@pytest.fixture()
def store(tmp_path, monkeypatch, fresh_db):
    monkeypatch.setattr(config, "STORAGE_DIR", tmp_path / "rec")
    yield


def test_conversation_helpers():
    assert conversation.band(90) == "high" and conversation.band(50) == "mid" and conversation.band(10) == "low"
    assert conversation.first_sentence("Great job. Add more detail.") == "Great job."
    assert conversation.reaction(90, "Nice. More.", use_feedback=True).endswith("Nice.")
    assert "Question 2." in conversation.next_turn("Thanks.", "Why?", 2, 5)
    assert "Final question." in conversation.next_turn("Thanks.", "Why?", 5, 5)
    assert "Hello Tanishq" in conversation.greeting("Tanishq", "Aria", "SQL", "What is a join?")
    assert "What is X?" in conversation.retry_prompt("What is X?")


def test_storage_roundtrip_and_path_safety(store):
    rel = storage.save_media(1, 2, 3, "video", b"abc123", "webm")
    assert rel.startswith("user_1/interview_2/q3_video_") and rel.endswith(".webm")
    assert storage.read_media(rel) == b"abc123"
    assert storage.total_size() == 6
    with pytest.raises(ValueError):
        storage.resolve("../../etc/passwd")
    storage.delete_media(rel)
    assert storage.read_media(rel) is None
    assert storage.ext_for("video/webm;codecs=vp8,opus") == "webm" and storage.ext_for("audio/mp4") == "m4a"


def test_recording_db_and_cleanup(store):
    u, _ = auth.create_user("rita", "Passw0rd1", "Rita")
    iid = db.create_interview(u["id"], "SQL", "Beginner", 1)
    db.save_answer(iid, 1, "q?", "a", "video", {"accuracy": 5, "depth": 5, "clarity": 5, "relevance": 5},
                   50, 0, 1, "ok", [], [])
    assert recordings.store_recording(u["id"], iid, 1, "q?", "a", None, None) is None   # no media -> nothing stored
    rid = recordings.store_recording(u["id"], iid, 1, "q?", "hello", b"VIDEO", b"AUDIO", "video/webm", "audio/webm", 12.34)
    df = db.recordings_df()
    assert len(df) == 1 and df.iloc[0]["username"] == "rita" and df.iloc[0]["score"] == 50
    row = db.get_recording(rid)
    assert storage.read_media(row["video_path"]) == b"VIDEO" and storage.read_media(row["audio_path"]) == b"AUDIO"
    assert db.get_recordings_for_interview(iid)[1]["transcript"] == "hello"
    assert db.delete_recordings([rid]) == 1 and storage.total_size() == 0
    # deleting a user removes their files too
    rid2 = recordings.store_recording(u["id"], iid, 1, "q?", "again", b"V2", None)
    path = db.get_recording(rid2)["video_path"]
    db.delete_user(u["id"])
    assert storage.read_media(path) is None and db.recordings_df().empty


def test_decode_b64_is_tolerant():
    import base64
    raw = b"\x1a\x45\xdf\xa3 webm bytes \x00\x01"
    good = base64.b64encode(raw).decode()
    assert recordings.decode_b64(good) == raw
    assert recordings.decode_b64(good.rstrip("=")) == raw                      # missing padding
    assert recordings.decode_b64(good[:10] + "\n" + good[10:]) == raw          # whitespace
    # the real-world bug: MIME type containing a comma, sent as a full data URL
    assert recordings.decode_b64("data:video/webm;codecs=vp8,opus;base64," + good) == raw
    assert recordings.decode_b64("") is None and recordings.decode_b64(None) is None
    assert recordings.decode_b64("opus;base64") is None                        # junk is rejected, never saved
