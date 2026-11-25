"""File storage for recorded answers (local disk; swap this module for S3/GCS in production)."""
import shutil
import time
from pathlib import Path

import config

EXT = {"video/webm": "webm", "video/mp4": "mp4", "audio/webm": "webm", "audio/mp4": "m4a",
       "audio/ogg": "ogg", "audio/wav": "wav"}


def _root() -> Path:
    config.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return config.STORAGE_DIR.resolve()


def ext_for(mime: str, default: str = "webm") -> str:
    return EXT.get((mime or "").split(";")[0].strip().lower(), default)


def save_media(user_id: int, interview_id: int, q_no: int, kind: str, data: bytes, ext: str) -> str:
    """Write bytes to storage and return the path relative to the storage root."""
    rel = Path(f"user_{int(user_id)}") / f"interview_{int(interview_id)}" / f"q{int(q_no)}_{kind}_{int(time.time())}.{ext}"
    full = _root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return rel.as_posix()


def resolve(rel: str) -> Path:
    """Resolve a stored relative path, refusing anything that escapes the storage root."""
    full = (_root() / rel).resolve()
    if _root() != full and _root() not in full.parents:
        raise ValueError("Invalid storage path")
    return full


def read_media(rel: str | None) -> bytes | None:
    if not rel:
        return None
    p = resolve(rel)
    return p.read_bytes() if p.exists() else None


def delete_media(rel: str | None) -> None:
    if not rel:
        return
    p = resolve(rel)
    if p.exists():
        p.unlink()
        for parent in (p.parent, p.parent.parent):  # tidy empty folders
            try:
                if parent != _root() and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass


def total_size() -> int:
    return sum(f.stat().st_size for f in _root().rglob("*") if f.is_file())


def wipe_all() -> None:
    shutil.rmtree(_root(), ignore_errors=True)
