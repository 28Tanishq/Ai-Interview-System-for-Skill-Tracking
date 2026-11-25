"""Save a recorded answer (video + audio files on disk, metadata in the database)."""
import base64
import binascii
import re

from core import database as db
from core import storage


def store_recording(user_id: int, interview_id: int, q_no: int, question: str, transcript: str,
                    video: bytes | None, audio: bytes | None, v_mime: str = "video/webm",
                    a_mime: str = "audio/webm", duration: float = 0.0) -> int | None:
    """Persist whatever media we received. Returns the recording id, or None if there was no media."""
    if not video and not audio:
        return None
    vpath = storage.save_media(user_id, interview_id, q_no, "video", video, storage.ext_for(v_mime)) if video else None
    apath = storage.save_media(user_id, interview_id, q_no, "audio", audio, storage.ext_for(a_mime)) if audio else None
    size = (len(video) if video else 0) + (len(audio) if audio else 0)
    return db.save_recording(interview_id, user_id, q_no, question, transcript, vpath, apath,
                             v_mime if video else a_mime, round(float(duration or 0), 1), size)


def decode_b64(data) -> bytes | None:
    """Decode base64 from the browser without ever raising.

    Accepts a plain base64 string or a full data URL, ignores whitespace and fixes missing padding.
    Returns None if the data is empty or cannot be decoded.
    """
    if not data:
        return None
    text = str(data)
    marker = ";base64,"
    if marker in text:                      # data URL: keep only what follows ';base64,'
        text = text.split(marker, 1)[1]
    text = re.sub(r"\s+", "", text)
    text += "=" * (-len(text) % 4)
    try:
        out = base64.b64decode(text, validate=True)   # reject non-base64 characters
    except (binascii.Error, ValueError):
        return None
    return out or None
