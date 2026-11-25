"""Python wrapper for the invisible proctoring component (window-violation detector)."""
import streamlit.components.v1 as components

import config

_proctor = components.declare_component("proctor", path=str(config.BASE_DIR / "components" / "proctor"))


def proctor_monitor(violations: int, limit: int, enabled: bool = True, key: str = "proctor"):
    """Render the detector. Returns None until a violation happens, then a dict:
    {type:'violation', id, kind, detail, n, ts}. `violations` is the server-side count (authoritative)."""
    return _proctor(violations=violations, limit=limit, enabled=enabled, grace_ms=config.PROCTOR_GRACE_MS,
                    key=key, default=None)
