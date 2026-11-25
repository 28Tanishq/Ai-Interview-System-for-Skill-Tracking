"""Admin console: user management, database connectivity, datasets."""
import pandas as pd
import plotly.express as px
import streamlit as st

import config
from core import auth, dataset, storage
from core import database as db
from core.theme import plot_in
from core.ui import setup_page

user = setup_page("Admin", "🛠️", require="admin")
st.markdown('<div class="hero"><h1>🛠️ Admin console</h1><p>Manage users, check the database and load data</p></div>',
            unsafe_allow_html=True)
t_users, t_rec, t_proc, t_db, t_data = st.tabs(["👥 Users", "🎥 Recordings", "🛡️ Proctoring", "🗄️ Database", "📦 Data & datasets"])

# ---------------------------------------------------------------------- Users
with t_users:
    users = db.users_with_stats_df()
    st.dataframe(users.drop(columns=["id"]), hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ Create user")
        with st.form("create_user", clear_on_submit=True):
            n_user = st.text_input("Username")
            n_name = st.text_input("Full name")
            n_mail = st.text_input("Email")
            n_role = st.selectbox("Role", ["candidate", "admin"])
            n_pw = st.text_input("Temporary password", type="password")
            if st.form_submit_button("Create", type="primary"):
                _, err = auth.create_user(n_user, n_pw, n_name, n_mail, n_role)
                st.error(err) if err else (st.success("User created."), st.rerun())
    with c2:
        st.subheader("✏️ Manage user")
        others = users[users["id"] != user["id"]]
        if others.empty:
            st.caption("No other users yet.")
        else:
            uname = st.selectbox("User", others["username"].tolist())
            row = others[others["username"] == uname].iloc[0]
            role = st.selectbox("Role", ["candidate", "admin"], index=["candidate", "admin"].index(row["role"]))
            active = st.toggle("Account active", value=bool(row["is_active"]))
            new_pw = st.text_input("Reset password (leave blank to keep)", type="password")
            if st.button("💾 Save changes"):
                db.update_user(int(row["id"]), role=role, is_active=int(active))
                if new_pw:
                    err = auth.set_password(int(row["id"]), new_pw)
                    if err:
                        st.error(err)
                        st.stop()
                st.success("Saved.")
                st.rerun()
            confirm = st.checkbox(f"I understand deleting @{uname} removes all their interviews")
            if st.button("🗑️ Delete user", disabled=not confirm):
                db.delete_user(int(row["id"]))
                st.success("Deleted.")
                st.rerun()

# ----------------------------------------------------------------- Recordings
with t_rec:
    rec = db.recordings_df()
    if rec.empty:
        st.info("No recordings yet. Audio/video answers appear here after candidates complete an "
                "**Avatar video interview**.")
    else:
        m = st.columns(4)
        m[0].metric("Recordings", len(rec))
        m[1].metric("Candidates", rec["username"].nunique())
        m[2].metric("Total answer time", f"{rec['duration_sec'].sum() / 60:.1f} min")
        m[3].metric("Storage used", f"{storage.total_size() / 1_048_576:.1f} MB")

        f1, f2, f3 = st.columns(3)
        who = f1.selectbox("Candidate", ["All"] + sorted(rec["username"].unique()))
        sk = f2.selectbox("Skill", ["All"] + sorted(rec["skill"].unique()))
        term = f3.text_input("Search transcript / question")
        view = rec.copy()
        if who != "All":
            view = view[view["username"] == who]
        if sk != "All":
            view = view[view["skill"] == sk]
        if term:
            hay = (view["transcript"].fillna("") + " " + view["question"].fillna("")).str.lower()
            view = view[hay.str.contains(term.lower(), regex=False)]
        view = view.assign(size_kb=(view["size_bytes"] / 1024).round(0))
        st.dataframe(view[["id", "username", "skill", "q_no", "score", "duration_sec", "size_kb", "created_at"]],
                     hide_index=True)

        if view.empty:
            st.warning("No recordings match the filters.")
        else:
            pick = st.selectbox("▶️ Open a recording", view["id"].tolist(), format_func=lambda i: (
                f"#{i} · @{view[view.id == i].iloc[0]['username']} · {view[view.id == i].iloc[0]['skill']} "
                f"· Q{view[view.id == i].iloc[0]['q_no']} · {view[view.id == i].iloc[0]['created_at']}"))
            row = view[view.id == pick].iloc[0]
            video = storage.read_media(row["video_path"])
            audio = storage.read_media(row["audio_path"])
            v, d = st.columns([3, 2], gap="large")
            with v:
                if video:
                    st.video(video)
                elif audio:
                    st.audio(audio)
                else:
                    st.warning("The media files for this recording are missing from storage.")
                if video and audio:
                    with st.expander("🎧 Audio-only track"):
                        st.audio(audio)
            with d:
                st.markdown(f"**Question:** {row['question']}")
                st.markdown("**Transcript**")
                st.write(row["transcript"] or "_none_")
                st.metric("Answer score", f"{row['score']:.1f}/100" if pd.notna(row["score"]) else "–")
                if video:
                    st.download_button("⬇️ Download video", video, file_name=f"rec_{pick}_{row['username']}.{row['video_path'].rsplit('.', 1)[-1]}")
                if audio:
                    st.download_button("⬇️ Download audio", audio, file_name=f"rec_{pick}_{row['username']}.{row['audio_path'].rsplit('.', 1)[-1]}")
                ok = st.checkbox("Confirm delete this recording", key=f"del_{pick}")
                if st.button("🗑️ Delete recording", disabled=not ok):
                    db.delete_recordings([int(pick)])
                    st.success("Deleted.")
                    st.rerun()

        with st.expander("🧹 Retention: delete old recordings"):
            days = st.number_input("Delete recordings older than (days)", min_value=1, value=90)
            old = rec[pd.to_datetime(rec["created_at"]) < pd.Timestamp.now() - pd.Timedelta(days=int(days))]
            st.caption(f"{len(old)} recording(s) would be deleted.")
            if st.button("Delete old recordings", disabled=old.empty):
                st.success(f"Deleted {db.delete_recordings(old['id'].tolist())} recording(s).")
                st.rerun()

# ----------------------------------------------------------------- Proctoring
with t_proc:
    st.caption(f"Proctoring is **{'ON' if config.PROCTORING_ENABLED else 'OFF'}**. Leaving the interview tab or window "
               f"counts as a violation; at **{config.MAX_VIOLATIONS}** the interview ends automatically "
               "(set MAX_VIOLATIONS / PROCTORING_ENABLED in .env).")
    vio = db.violations_df()
    if vio.empty:
        st.info("No window violations have been recorded yet.")
    else:
        auto_ended = vio[vio["end_reason"] == "violations"]["interview_id"].nunique()
        m = st.columns(4)
        m[0].metric("Violations logged", len(vio))
        m[1].metric("Candidates flagged", vio["username"].nunique())
        m[2].metric("Interviews auto-ended", auto_ended)
        m[3].metric("Limit per interview", config.MAX_VIOLATIONS)
        c1, c2 = st.columns(2)
        by_user = vio.groupby("username").size().reset_index(name="violations")
        plot_in(c1, px.bar(by_user, x="username", y="violations", title="Violations by candidate"))
        by_kind = vio.groupby("kind").size().reset_index(name="count")
        plot_in(c2, px.pie(by_kind, names="kind", values="count", title="By type"))
        who = st.selectbox("Candidate", ["All"] + sorted(vio["username"].unique()), key="vio_user")
        view = vio if who == "All" else vio[vio["username"] == who]
        st.dataframe(view[["created_at", "username", "skill", "interview_id", "kind", "detail", "interview_violations",
                           "end_reason"]], hide_index=True)
        st.download_button("⬇️ Export violation log (CSV)", view.to_csv(index=False).encode("utf-8"),
                           file_name="violations_log.csv", mime="text/csv")

# ------------------------------------------------------------------- Database
with t_db:
    st.subheader("Connection")
    ok, msg, ms = db.test_connection()
    (st.success if ok else st.error)(f"{msg} · {ms:.1f} ms" if ok else msg)
    st.code(db.safe_url(), language="text")
    counts = db.table_counts()
    cols = st.columns(len(counts))
    for col, (t, n) in zip(cols, counts.items()):
        col.metric(t, n)
    f = db.sqlite_file()
    if f and f.exists():
        st.caption(f"SQLite file: `{f}` · {f.stat().st_size / 1024:.0f} KB")
        st.download_button("⬇️ Download database backup", f.read_bytes(), file_name=f.name)

    st.subheader("Test another database")
    st.caption("Example: `postgresql+psycopg2://user:password@host:5432/dbname` (needs `pip install psycopg2-binary`). "
               "To switch permanently, set `DATABASE_URL` in `.env` and restart.")
    url = st.text_input("SQLAlchemy URL", placeholder="postgresql+psycopg2://user:pass@localhost:5432/skilltracker")
    if st.button("🔌 Test connection") and url:
        ok2, msg2, ms2 = db.test_connection(url)
        (st.success if ok2 else st.error)(f"{msg2} · {ms2:.1f} ms" if ok2 else msg2)

# ------------------------------------------------------------------- Datasets
with t_data:
    st.subheader("Example dataset")
    st.write("Imports 5 demo candidates (alice, bob, carol, dave, eve), about 70 interviews and 345 answers. "
             f"Demo password: `{config.DEMO_PASSWORD}`. Safe to run more than once.")
    shift = st.checkbox("Shift dates so the newest session is yesterday", value=True)
    if st.button("📥 Load example dataset", type="primary"):
        with st.spinner("Importing…"):
            res = dataset.load_sample(shift_dates=shift)
        st.success(f"Imported {res['users']} users, {res['interviews']} interviews, {res['answers']} answers.")

    st.subheader("Import your own CSVs")
    st.caption("Columns must match the files in `data/sample_dataset/`.")
    u1, u2, u3 = st.columns(3)
    fu, fi, fa = (u1.file_uploader("users.csv", type="csv"), u2.file_uploader("interviews.csv", type="csv"),
                  u3.file_uploader("answers.csv", type="csv"))
    if fu and fi and fa and st.button("Import uploaded CSVs"):
        try:
            res = dataset.import_dataset(pd.read_csv(fu), pd.read_csv(fi), pd.read_csv(fa), shift_dates=False)
            st.success(f"Imported {res['users']} users, {res['interviews']} interviews, {res['answers']} answers.")
        except Exception as e:  # noqa: BLE001
            st.error(str(e))

    st.subheader("Export")
    e1, e2 = st.columns(2)
    e1.download_button("⬇️ All interviews (CSV)", db.get_all_interviews_df().to_csv(index=False).encode(),
                       file_name="interviews_export.csv")
    e2.download_button("⬇️ All answers (CSV)", db.get_all_answers_df().to_csv(index=False).encode(),
                       file_name="answers_export.csv")

    with st.expander("⚠️ Danger zone"):
        sure = st.checkbox("Delete every non-admin user and all interview data")
        if st.button("🧨 Wipe data", disabled=not sure):
            db.wipe_data(keep_admins=True)
            st.success("All candidate data removed.")
            st.rerun()
