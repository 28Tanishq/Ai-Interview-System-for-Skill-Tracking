"""Shared Streamlit shell: page setup, theme, login gate, sidebar and small UI building blocks."""
import streamlit as st

import config
from core import auth, dataset, theme
from core import database as db
from core.ai_engine import AIEngine

STEPS = ["1 · Choose skill", "2 · Configure", "3 · Interview", "4 · Report"]


@st.cache_resource
def get_engine() -> AIEngine:
    return AIEngine()


@st.cache_resource
def _bootstrap() -> bool:
    """Once per server process: create tables, admin account and (optionally) example data."""
    db.init_db()
    auth.ensure_admin()
    if config.AUTO_LOAD_SAMPLE and db.table_counts()["interviews"] == 0:
        try:
            dataset.load_sample()
        except Exception as e:  # noqa: BLE001  never block startup on sample data
            print("Sample data load failed:", e)
    return True


# ------------------------------------------------------------------ building blocks
def hero(title: str, subtitle: str = "", danger: bool = False) -> None:
    st.markdown(f'<div class="hero {"danger" if danger else ""}"><h1>{title}</h1><p>{subtitle}</p></div>',
                unsafe_allow_html=True)


def stepper(active: int) -> None:
    """Progress header: active is 0..3."""
    items = "".join(
        f'<div class="step {"active" if i == active else "done" if i < active else ""}">{label}</div>'
        for i, label in enumerate(STEPS))
    st.markdown(f'<div class="steps">{items}</div>', unsafe_allow_html=True)


def chips(items: list[tuple[str, str]]) -> None:
    """items: [(text, kind)] where kind is '', 'ok', 'warn' or 'bad'."""
    st.markdown("".join(f'<span class="chip {k}">{t}</span>' for t, k in items), unsafe_allow_html=True)


def card(html: str, extra_class: str = "") -> None:
    st.markdown(f'<div class="card {extra_class}">{html}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------------ page shell
def setup_page(title: str, icon: str, require: str = "user") -> dict:
    """Configure the page, apply the theme, enforce login (require='user'|'admin'), draw sidebar, return the user."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide", initial_sidebar_state="expanded")
    theme.inject()
    try:
        _bootstrap()
    except Exception as e:  # noqa: BLE001
        st.error(f"❌ Cannot connect to the database: {e}")
        st.caption(f"Configured URL: `{db.safe_url()}`. Check DATABASE_URL in your .env file.")
        st.stop()
    user = auth.require_login()
    if require == "admin" and user["role"] != "admin":
        st.error("🔒 This page is for administrators only.")
        st.stop()
    _sidebar(user)
    return user


def _sidebar(user: dict) -> None:
    engine = get_engine()
    initial = (user["full_name"] or user["username"])[:1].upper()
    with st.sidebar:
        st.markdown("#### 🎙️ SkillTracker AI")
        theme.toggle()
        st.markdown(
            f'<div style="display:flex;align-items:center;margin:.6rem 0">'
            f'<span class="avatar-dot">{initial}</span><div><b>{user["full_name"] or user["username"]}</b><br>'
            f'<span class="badge {"admin" if user["role"] == "admin" else ""}">{user["role"]}</span> '
            f'<span style="opacity:.7">@{user["username"]}</span></div></div>', unsafe_allow_html=True)
        if st.button("🚪 Log out", key="logout_btn"):
            auth.logout()
        with st.expander("🔑 Change password"):
            with st.form("pw_form", clear_on_submit=True):
                old = st.text_input("Current password", type="password")
                new = st.text_input("New password", type="password")
                if st.form_submit_button("Update"):
                    err = auth.change_password(user["id"], old, new)
                    st.error(err) if err else st.success("Password updated.")
        st.divider()
        if engine.online:
            st.success(f"AI: Gemini connected · `{engine.model}`", icon="🤖")
        else:
            st.warning("AI offline mode: using the built-in question bank. Add GEMINI_API_KEY for full AI.", icon="📴")
        if engine.last_error:
            st.caption(f"⚠️ {engine.last_error[:160]}")
        with st.expander("🎧 Voice settings"):
            label = st.selectbox("Recognition language", list(config.SPEECH_LANGUAGES), index=1)
            st.session_state["speech_lang"] = config.SPEECH_LANGUAGES[label]
            st.session_state["tts"] = st.toggle("Read questions aloud (classic mode)", value=True)
