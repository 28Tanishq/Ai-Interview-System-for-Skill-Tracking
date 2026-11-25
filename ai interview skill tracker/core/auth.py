"""Authentication: salted PBKDF2 password hashing, registration, login UI, roles."""
import hashlib
import hmac
import re
import secrets
import time

import streamlit as st

import config
from core import database as db

USERNAME_RE = re.compile(r"^[a-z0-9_.-]{3,30}$")
PBKDF2_ITERATIONS = 200_000


# ------------------------------------------------------------------- pure logic
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, digest: str, salt: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt)[0], digest)


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must contain both letters and numbers."
    return None


def create_user(username: str, password: str, full_name: str = "", email: str = "",
                role: str = "candidate") -> tuple[dict | None, str | None]:
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        return None, "Username must be 3-30 characters: letters, numbers, dot, dash or underscore."
    if (err := validate_password(password)):
        return None, err
    if role not in ("candidate", "admin"):
        return None, "Invalid role."
    if db.get_user_by_username(username):
        return None, "That username is already taken."
    h, s = hash_password(password)
    uid = db.create_user_row(username, h, s, full_name.strip(), email.strip(), role)
    return db.get_user(uid), None


def authenticate(username: str, password: str) -> tuple[dict | None, str | None]:
    user = db.get_user_by_username(username or "")
    if not user or not verify_password(password or "", user["password_hash"], user["salt"]):
        return None, "Invalid username or password."
    if not user["is_active"]:
        return None, "This account has been deactivated. Contact an administrator."
    db.touch_login(user["id"])
    return db.get_user(user["id"]), None


def change_password(user_id: int, old: str, new: str) -> str | None:
    user = db.get_user(user_id)
    if not verify_password(old, user["password_hash"], user["salt"]):
        return "Current password is incorrect."
    return set_password(user_id, new)


def set_password(user_id: int, new: str) -> str | None:
    if (err := validate_password(new)):
        return err
    h, s = hash_password(new)
    db.update_user(user_id, password_hash=h, salt=s)
    return None


def ensure_admin() -> None:
    if not db.get_user_by_username(config.ADMIN_USERNAME):
        h, s = hash_password(config.ADMIN_PASSWORD)
        db.create_user_row(config.ADMIN_USERNAME, h, s, "Administrator", "", "admin")


# ----------------------------------------------------------------------- UI
def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def logout() -> None:
    dark = st.session_state.get("dark_mode", False)
    st.session_state.clear()
    st.session_state["dark_mode"] = dark      # keep the chosen theme after signing out
    st.rerun()


def _render_login() -> None:
    S = st.session_state
    from core import theme
    _, tcol = st.columns([5, 1])
    with tcol:
        theme.toggle()
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown(
            '<div class="hero" style="padding:2.2rem 2rem"><h1>🎙️ SkillTracker AI</h1>'
            '<p>Practise spoken interviews with an AI interviewer, get instant feedback and watch your skills grow.</p></div>'
            '<div class="card"><h4>What you get</h4><ul>'
            '<li>🧑‍💼 A talking avatar interviewer that adapts to your answers</li>'
            '<li>🎥 Camera and voice answers, recorded for your review</li>'
            '<li>📊 Scores, skill levels and progress dashboards</li>'
            '<li>🏆 A leaderboard to compare with other candidates</li>'
            '<li>🛡️ Fair, proctored sessions: stay on the interview window</li></ul></div>', unsafe_allow_html=True)
    with right:
        t_in, t_reg = st.tabs(["🔐 Sign in", "📝 Create account"])
        with t_in:
            with st.form("login_form"):
                u = st.text_input("Username", placeholder="e.g. alice")
                p = st.text_input("Password", type="password")
                go = st.form_submit_button("Sign in", type="primary")
            if go:
                wait = S.get("lock_until", 0) - time.time()
                if wait > 0:
                    st.error(f"Too many failed attempts. Try again in {int(wait) + 1}s.")
                else:
                    user, err = authenticate(u, p)
                    if err:
                        S["fails"] = S.get("fails", 0) + 1
                        if S["fails"] >= config.MAX_LOGIN_ATTEMPTS:
                            S["lock_until"] = time.time() + config.LOCKOUT_SECONDS
                            S["fails"] = 0
                        st.error(err)
                    else:
                        S["auth_user"] = user
                        st.rerun()
        with t_reg:
            with st.form("register_form"):
                name = st.text_input("Full name")
                email = st.text_input("Email (optional)")
                ru = st.text_input("Choose a username")
                p1 = st.text_input("Password (8+ chars, letters and numbers)", type="password")
                p2 = st.text_input("Confirm password", type="password")
                go = st.form_submit_button("Create account", type="primary")
            if go:
                if p1 != p2:
                    st.error("Passwords do not match.")
                else:
                    user, err = create_user(ru, p1, name, email)
                    if err:
                        st.error(err)
                    else:
                        S["auth_user"] = user
                        st.success("Account created!")
                        st.rerun()
        if config.SHOW_DEMO_HINT and db.get_user_by_username("alice"):
            with st.expander("🧪 Demo accounts (example dataset)"):
                st.markdown(f"""| Username | Password | Role |
|---|---|---|
| `{config.ADMIN_USERNAME}` | `{config.ADMIN_PASSWORD}` | Admin (sees everyone) |
| `alice`, `bob`, `carol`, `dave`, `eve` | `{config.DEMO_PASSWORD}` | Candidates with history |""")


def require_login() -> dict:
    """Return the logged-in user or show the login screen and stop the script."""
    user = current_user()
    if user is None:
        _render_login()
        st.stop()
    fresh = db.get_user(user["id"])
    if fresh is None or not fresh["is_active"]:
        st.session_state.clear()
        st.rerun()
    st.session_state["auth_user"] = fresh
    return fresh
