"""Python wrapper for the interview-room browser component (talking avatar + camera/mic recorder)."""
import streamlit.components.v1 as components

import config

_room = components.declare_component("interview_room", path=str(config.BASE_DIR / "components" / "interview_room"))


def interview_room(say: str, say_id: str, record: bool, lang: str = "en-US", rate: float = 1.0, key: str = "room"):
    """Render the room. The avatar speaks `say` (once per `say_id`), then records the answer if `record`.

    Returns None until the browser finishes an answer, then a dict:
    {type:'answer', id, transcript, video_b64, audio_b64, v_mime, a_mime, duration, reason}
    or {type:'error', error, id} if camera/microphone access failed.
    """
    return _room(say=say, say_id=say_id, record=record, lang=lang, rate=rate, avatar_name=config.AVATAR_NAME,
                 max_seconds=config.MAX_ANSWER_SECONDS, silence_seconds=config.SILENCE_SECONDS,
                 no_speech_seconds=config.NO_SPEECH_SECONDS, key=key, default=None)
