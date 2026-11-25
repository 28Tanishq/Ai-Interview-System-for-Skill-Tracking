"""Progress dashboard: personal analytics, skills, history, leaderboard, and (admin) cohort view."""
import pandas as pd
import plotly.express as px
import streamlit as st

from core import database as db
from core import storage
from core import scoring
from core.charts import radar
from core.theme import plot_in
from core.ui import setup_page

user = setup_page("Dashboard", "📊")
is_admin = user["role"] == "admin"

target = user
if is_admin:
    people = db.list_users()
    names = {u["id"]: f"{u['full_name'] or u['username']} (@{u['username']})" for u in people}
    ids = list(names)
    st.session_state.setdefault("dash_user", user["id"])
    sel = st.sidebar.selectbox("👁️ View dashboard of", ids, format_func=names.get, key="dash_user")
    target = next(u for u in people if u["id"] == sel)

tname = target["full_name"] or target["username"]
st.markdown(f'<div class="hero"><h1>📊 {tname}</h1><p>Skill progress, trends and rankings</p></div>',
            unsafe_allow_html=True)

interviews = db.get_interviews_df(target["id"])
answers = db.get_answers_df(target["id"])
prof_all = db.get_proficiency_df(target["id"])
has_data = not interviews.empty

# ---------------------------------------------------------------- filters
iv, an, prof = interviews, answers, prof_all
if has_data:
    with st.expander("🔎 Filters", expanded=False):
        f1, f2 = st.columns(2)
        skills_all = sorted(interviews["skill"].unique())
        sel_skills = f1.multiselect("Skills", skills_all, default=skills_all)
        dmin, dmax = interviews["started_at"].min().date(), interviews["started_at"].max().date()
        rng = f2.date_input("Date range", value=(dmin, dmax), min_value=dmin, max_value=dmax) if dmin < dmax else (dmin, dmax)
        if len(rng) != 2:
            rng = (dmin, dmax)
    mask = (interviews["skill"].isin(sel_skills) & (interviews["started_at"].dt.date >= rng[0])
            & (interviews["started_at"].dt.date <= rng[1]))
    iv = interviews[mask].copy()
    an = answers[answers["interview_id"].isin(iv["id"])].copy()
    prof = prof_all[prof_all["skill"].isin(sel_skills)]

tabs = st.tabs(["📈 Overview", "🧠 Skills", "🗂️ History", "🏆 Leaderboard"] + (["👥 Cohort (admin)"] if is_admin else []))


def need_data() -> bool:
    if not has_data:
        st.info("No completed interviews yet for this user. Take an interview on the home page"
                + (", or load the example dataset from **Admin → Data & datasets**." if is_admin else "."))
        return True
    if iv.empty:
        st.warning("No interviews match the current filters.")
        return True
    return False


# ------------------------------------------------------------------ Overview
with tabs[0]:
    if not need_data():
        half = max(1, len(iv) // 2)
        delta = iv["overall_score"].iloc[-half:].mean() - iv["overall_score"].iloc[:half].mean() if len(iv) > 1 else 0
        k = st.columns(5)
        k[0].metric("Interviews", len(iv))
        k[1].metric("Average score", f"{iv['overall_score'].mean():.1f}")
        k[2].metric("Best score", f"{iv['overall_score'].max():.1f}")
        k[3].metric("Trend (recent vs early)", f"{delta:+.1f} pts", delta=f"{delta:+.1f}")
        sp = an[an["word_count"] > 0]
        k[4].metric("Filler words / 100", f"{(sp['filler_count'].sum() / max(1, sp['word_count'].sum()) * 100):.1f}")

        st.subheader("Score trend")
        show_avg = st.toggle("Overlay 3-session moving average", value=True)
        fig = px.line(iv, x="started_at", y="overall_score", color="skill", markers=True,
                      labels={"started_at": "Date", "overall_score": "Score", "skill": "Skill"})
        if show_avg and len(iv) >= 3:
            ma = iv["overall_score"].rolling(3, min_periods=1).mean()
            fig.add_scatter(x=iv["started_at"], y=ma, mode="lines", name="Moving avg",
                            line=dict(color="black", dash="dash"))
        fig.update_yaxes(range=[0, 100])
        plot_in(st, fig)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Weekly activity")
            wk = iv.set_index("started_at").resample("W")["id"].count().reset_index(name="sessions")
            plot_in(st, px.bar(wk, x="started_at", y="sessions", labels={"started_at": "Week"}))
        with c2:
            st.subheader("Answer score distribution")
            plot_in(st, px.histogram(an, x="overall", nbins=10, labels={"overall": "Answer score"}))

# -------------------------------------------------------------------- Skills
with tabs[1]:
    if not need_data():
        left, right = st.columns(2)
        with left:
            st.subheader("Proficiency map")
            if len(prof) >= 3:
                plot_in(st, radar(prof["skill"].tolist(), prof["proficiency"].tolist()))
            else:
                plot_in(st, px.bar(prof, x="skill", y="proficiency", range_y=[0, 100]))
        with right:
            st.subheader("Skill levels")
            tbl = prof.copy()
            tbl["level"] = tbl["proficiency"].apply(scoring.level_for)
            st.dataframe(tbl[["skill", "proficiency", "level", "sessions"]].sort_values("proficiency", ascending=False),
                         hide_index=True,
                         column_config={"proficiency": st.column_config.ProgressColumn(
                             "Proficiency", min_value=0, max_value=100, format="%.0f")})
            low = prof.sort_values("proficiency").iloc[0]
            st.success(f"🎯 Recommended focus: **{low['skill']}** ({low['proficiency']:.0f}/100)")

        st.subheader("Rubric breakdown")
        rub = an.groupby("skill")[["accuracy", "depth", "clarity", "relevance"]].mean().reset_index()
        plot_in(st, px.bar(rub.melt(id_vars="skill", var_name="criterion", value_name="score"),
                               x="skill", y="score", color="criterion", barmode="group", range_y=[0, 10]))

        st.subheader("Skill deep-dive")
        one = st.selectbox("Pick a skill", sorted(iv["skill"].unique()))
        sk_iv, sk_an = iv[iv["skill"] == one], an[an["skill"] == one]
        d1, d2 = st.columns(2)
        plot_in(d1, px.line(sk_iv, x="started_at", y="overall_score", markers=True, range_y=[0, 100],
                                labels={"started_at": "Date", "overall_score": "Score"}))
        d2.markdown("**Questions to revisit**")
        d2.dataframe(sk_an.sort_values("overall").head(5)[["question", "overall"]], hide_index=True)

# ------------------------------------------------------------------- History
with tabs[2]:
    if not need_data():
        hist = iv[["id", "started_at", "skill", "difficulty", "overall_score", "ai_mode"]].sort_values(
            "started_at", ascending=False)
        st.dataframe(hist, hide_index=True)
        pick = st.selectbox("🔍 Inspect a session", hist["id"].tolist(), format_func=lambda i: (
            f"#{i} · {hist[hist.id == i].iloc[0]['skill']} · {hist[hist.id == i].iloc[0]['started_at']:%d %b %Y}"))
        st.write(iv[iv.id == pick].iloc[0]["summary"])
        recs = db.get_recordings_for_interview(int(pick))
        for _, a in an[an["interview_id"] == pick].iterrows():
            with st.expander(f"Q{a['q_no']}: {a['question']} — {a['overall']}/100"):
                st.write(f"**Answer:** {a['answer'] or '_skipped_'}")
                st.write(f"**Feedback:** {a['feedback']}")
                r = recs.get(int(a["q_no"]))
                if r:
                    media = storage.read_media(r["video_path"])
                    if media:
                        st.video(media)
                    elif r["audio_path"] and (audio := storage.read_media(r["audio_path"])):
                        st.audio(audio)
        st.download_button("⬇️ Export answers (CSV)", an.to_csv(index=False).encode("utf-8"),
                           file_name=f"{target['username']}_answers.csv", mime="text/csv")
        term = db.get_terminated_df(target["id"])
        if not term.empty:
            st.subheader("⛔ Interviews ended automatically (window violations)")
            st.caption("These attempts are not scored and are excluded from trends and rankings.")
            st.dataframe(term[["started_at", "skill", "difficulty", "violations", "summary"]], hide_index=True)

# --------------------------------------------------------------- Leaderboard
with tabs[3]:
    lb = db.leaderboard_df()
    if lb.empty:
        st.info("No one has completed an interview yet.")
    else:
        me = lb[lb["user_id"] == target["id"]]
        if len(me):
            m1, m2 = st.columns(2)
            m1.metric("Rank", f"#{int(me.iloc[0]['rank'])} of {len(lb)}")
            m2.metric("Average score", me.iloc[0]["avg_score"])
        lb["you"] = lb["user_id"].map(lambda i: "Selected user" if i == target["id"] else "Others")
        plot_in(st, px.bar(lb, x="display", y="avg_score", color="you", range_y=[0, 100],
                               color_discrete_map={"Selected user": "#6C5CE7", "Others": "#b2bec3"},
                               labels={"display": "Candidate", "avg_score": "Average score"}))
        st.dataframe(lb[["rank", "display", "sessions", "avg_score", "best_score"]], hide_index=True)
        st.subheader("By skill")
        allp = db.get_all_proficiency_df()
        s_pick = st.selectbox("Skill", sorted(allp["skill"].unique()), key="lb_skill")
        sp = allp[allp["skill"] == s_pick].sort_values("proficiency", ascending=False).reset_index(drop=True)
        sp["Candidate"] = sp["full_name"].where(sp["full_name"].astype(bool), sp["username"])
        st.dataframe(sp[["Candidate", "proficiency", "sessions"]], hide_index=True,
                     column_config={"proficiency": st.column_config.ProgressColumn(
                         "Proficiency", min_value=0, max_value=100, format="%.0f")})

# ---------------------------------------------------------------- Cohort
if is_admin:
    with tabs[4]:
        all_iv = db.get_all_interviews_df()
        if all_iv.empty:
            st.info("No data yet. Load the example dataset from Admin → Data & datasets.")
        else:
            recent = all_iv[all_iv["started_at"] > pd.Timestamp.now() - pd.Timedelta(days=30)]
            k = st.columns(4)
            k[0].metric("Candidates", all_iv["username"].nunique())
            k[1].metric("Total interviews", len(all_iv))
            k[2].metric("Cohort average", f"{all_iv['overall_score'].mean():.1f}")
            k[3].metric("Active (30 days)", recent["username"].nunique())
            c1, c2 = st.columns(2)
            c1.subheader("Average score by skill")
            plot_in(c1, px.bar(all_iv.groupby("skill")["overall_score"].mean().reset_index(),
                                   x="skill", y="overall_score", range_y=[0, 100]))
            c2.subheader("Interviews per candidate")
            plot_in(c2, px.bar(all_iv.groupby("username")["id"].count().reset_index(name="interviews"),
                                   x="username", y="interviews"))
            st.subheader("Proficiency heat-map (candidate × skill)")
            allp = db.get_all_proficiency_df()
            pivot = allp.pivot_table(index="username", columns="skill", values="proficiency")
            plot_in(st, px.imshow(pivot, text_auto=".0f", color_continuous_scale="RdYlGn", zmin=0, zmax=100,
                                      aspect="auto"))
            st.subheader("Cohort score trend")
            mo = all_iv.set_index("started_at").resample("W")["overall_score"].mean().reset_index()
            plot_in(st, px.line(mo, x="started_at", y="overall_score", markers=True, range_y=[0, 100]))
