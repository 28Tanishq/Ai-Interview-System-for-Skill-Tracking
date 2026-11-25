"""Light / dark theme: design tokens, CSS injection, toggle widget and theme-aware Plotly charts.

Streamlit has no runtime theme switch, so both themes are applied with CSS on top of a light base theme
(see .streamlit/config.toml). The choice lives in st.session_state["dark_mode"].
"""
import streamlit as st

TOKENS = {
    "light": dict(bg="#f4f6fb", surface="#ffffff", text="#1b2133", muted="#5d667a", border="rgba(25,30,50,.13)",
                  sidebar="#ffffff", input="#ffffff", shadow="rgba(40,50,90,.10)", scheme="light"),
    "dark": dict(bg="#0e1120", surface="#171b30", text="#e9ebf5", muted="#a2a9c3", border="rgba(255,255,255,.13)",
                 sidebar="#121528", input="#1f2440", shadow="rgba(0,0,0,.45)", scheme="dark"),
}

CSS = """
<style>
:root{--bg:@bg;--surface:@surface;--text:@text;--muted:@muted;--border:@border;--sidebar:@sidebar;--input:@input;
      --shadow:@shadow;--accent:#6C5CE7;--accent2:#00b4d8;color-scheme:@scheme}
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:var(--bg)!important;color:var(--text)!important}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"],[data-testid="stSidebar"]>div:first-child{background:var(--sidebar)!important;border-right:1px solid var(--border)}
.block-container{padding-top:1.6rem;max-width:1250px}

/* text */
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp h5,.stApp h6{color:var(--text)!important;letter-spacing:-.01em}
.stApp [data-testid="stMarkdownContainer"] p,.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] td,.stApp [data-testid="stMarkdownContainer"] th,
.stApp label,.stApp [data-testid="stWidgetLabel"] p,.stApp [data-testid="stMetricValue"],
.stApp [data-testid="stMetricLabel"] p,.stApp summary,.stApp [data-testid="stSpinner"] p{color:var(--text)}
.stApp [data-testid="stCaptionContainer"],.stApp [data-testid="stCaptionContainer"] p{color:var(--muted)!important}
.stApp .hero h1,.stApp .hero p{color:#fff!important}

/* inputs */
.stApp input,.stApp textarea,.stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"]>div{background:var(--input)!important;color:var(--text)!important;border-color:var(--border)!important}
.stApp [data-baseweb="input"] input,.stApp textarea{-webkit-text-fill-color:var(--text)}
.stApp [data-baseweb="select"] *{color:var(--text)}
[data-baseweb="popover"],[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:var(--surface)!important;color:var(--text)!important}
[data-baseweb="popover"] li{color:var(--text)!important}
[data-baseweb="popover"] li:hover{background:rgba(128,128,128,.18)!important}
.stApp input:focus,.stApp textarea:focus{box-shadow:0 0 0 2px rgba(108,92,231,.45)!important}

/* buttons */
.stButton>button,.stDownloadButton>button,[data-testid="stFormSubmitButton"]>button,[data-testid="stBaseButton-secondary"]{
  background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:10px;font-weight:600;
  transition:transform .12s ease,box-shadow .12s ease,border-color .12s ease}
.stButton>button:hover,.stDownloadButton>button:hover,[data-testid="stBaseButton-secondary"]:hover{
  transform:translateY(-1px);box-shadow:0 6px 16px var(--shadow);border-color:var(--accent);color:var(--text)}
.stButton>button[kind="primary"],[data-testid="stBaseButton-primary"],[data-testid="stFormSubmitButton"]>button[kind="primaryFormSubmit"]{
  background:linear-gradient(120deg,#6C5CE7,#8f7df2)!important;color:#fff!important;border:0!important}
.stButton>button:disabled{opacity:.5;transform:none;box-shadow:none}
.stButton>button:focus-visible,.stApp input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* cards, metrics, expanders, tabs */
[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);padding:.8rem 1rem;border-radius:14px;
  box-shadow:0 2px 10px var(--shadow)}
[data-testid="stExpander"] details{background:var(--surface);border:1px solid var(--border);border-radius:12px}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--border)!important;border-radius:14px}
[data-testid="stForm"]{background:var(--surface);border:1px solid var(--border);border-radius:14px}
button[data-baseweb="tab"]{color:var(--muted);font-weight:600}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--accent)}
[data-testid="stAlert"],[data-testid="stAlert"]>div{border-radius:12px}

.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:1rem 1.25rem;
  box-shadow:0 2px 10px var(--shadow);color:var(--text)}
.card h4{margin:.1rem 0 .4rem 0}
.card ul{margin:.3rem 0 0 1.1rem;padding:0}
.rules{border-left:5px solid #e67e22}
.hero{background:linear-gradient(120deg,#6C5CE7 0%,#8e7cf0 55%,#00b4d8 100%);color:#fff;padding:1.5rem 2rem;
  border-radius:18px;margin-bottom:1rem;box-shadow:0 10px 30px rgba(108,92,231,.28)}
.hero h1{margin:0 0 .25rem 0;font-size:2rem;padding:0}
.hero p{margin:0;opacity:.93;font-size:1.05rem}
.hero.danger{background:linear-gradient(120deg,#c0392b 0%,#e67e22 100%);box-shadow:0 10px 30px rgba(192,57,43,.3)}
.qcard{border-left:6px solid var(--accent);background:rgba(108,92,231,.10);padding:1rem 1.3rem;border-radius:12px;
  font-size:1.2rem;font-weight:600;margin:.4rem 0 1rem 0;color:var(--text)}
.chip{display:inline-block;padding:.22rem .75rem;border-radius:999px;font-size:.8rem;font-weight:700;margin:0 6px 6px 0;
  background:rgba(108,92,231,.15);color:var(--accent)}
.chip.ok{background:rgba(46,204,113,.16);color:#22a559}
.chip.warn{background:rgba(243,156,18,.2);color:#d68910}
.chip.bad{background:rgba(231,76,60,.18);color:#e74c3c}
.badge{display:inline-block;padding:.12rem .6rem;border-radius:999px;font-size:.72rem;font-weight:700;
  background:rgba(108,92,231,.18);color:var(--accent)}
.badge.admin{background:rgba(231,76,60,.15);color:#e74c3c}
.avatar-dot{display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:50%;
  background:linear-gradient(135deg,#6C5CE7,#00b4d8);color:#fff;font-weight:800;font-size:1.1rem;margin-right:.6rem}
.steps{display:flex;gap:8px;margin:.2rem 0 1rem 0;flex-wrap:wrap}
.step{flex:1;min-width:110px;padding:.5rem .8rem;border-radius:10px;background:var(--surface);border:1px solid var(--border);
  color:var(--muted);font-weight:700;font-size:.85rem;text-align:center}
.step.active{background:linear-gradient(120deg,#6C5CE7,#8f7df2);color:#fff;border:0;box-shadow:0 4px 14px rgba(108,92,231,.35)}
.step.done{color:var(--accent);border-color:var(--accent)}
.skill-emoji{font-size:1.8rem;line-height:1}
@media (max-width:640px){.hero{padding:1.1rem 1.2rem}.hero h1{font-size:1.5rem}.block-container{padding-left:.8rem;padding-right:.8rem}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
"""

DARK_EXTRA = """
<style>
/* dark mode: widgets Streamlit draws itself */
[data-testid="stAlert"],[data-testid="stAlert"]>div{background:rgba(108,92,231,.16)!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"])>div{background:rgba(46,204,113,.16)!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"])>div{background:rgba(243,156,18,.18)!important}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),[data-testid="stAlert"]:has([data-testid="stAlertContentError"])>div{background:rgba(231,76,60,.2)!important}
[data-testid="stDataFrame"],[data-testid="stTable"]{filter:invert(.92) hue-rotate(180deg)}
[data-testid="stAudioInput"],audio,video{color-scheme:dark}
.stApp code{background:rgba(255,255,255,.08);color:#ffd9a8}
</style>
"""


def is_dark() -> bool:
    return bool(st.session_state.get("dark_mode", False))


def inject() -> None:
    """Call once per run, before drawing anything."""
    st.session_state.setdefault("dark_mode", False)
    t = TOKENS["dark" if is_dark() else "light"]
    css = CSS
    for k, v in t.items():
        css = css.replace("@" + k + ";", v + ";").replace("@" + k + "}", v + "}").replace("@" + k + ")", v + ")")
    st.markdown(css + (DARK_EXTRA if is_dark() else ""), unsafe_allow_html=True)


def toggle(label: str = "🌙 Dark mode") -> None:
    """The dark/light switch. Render it at most once per run (it owns the 'dark_mode' key)."""
    st.toggle(label, key="dark_mode", help="Switch between light and dark appearance")


def style_fig(fig):
    dark = is_dark()
    fig.update_layout(template="plotly_dark" if dark else "plotly_white", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e9ebf5" if dark else "#1b2133"))
    return fig


def plot_in(container, fig, **kw) -> None:
    """Draw a Plotly figure in `container` (st or a column) using the active theme."""
    container.plotly_chart(style_fig(fig), theme=None, **kw)
