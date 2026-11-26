# Ai-Interview-System-for-Skill-Tracking


### 🎓 Mentorship & Guidance

We are sincerely grateful to **Dr. K. C. Bandhu**, our project guide, for his invaluable mentorship, technical guidance, and continuous encouragement throughout the development journey.

We would also like to extend our appreciation to **Ms. Yashashvi Sharma**, our senior, for her consistent support, valuable insights, and assistance at every stage of the project. Her guidance played an important role in helping us navigate challenges and move forward with confidence.

### 🏛️ With Gratitude

We extend our heartfelt appreciation to the **Medi-Caps University family**, faculty members, friends, and everyone who supported and encouraged us throughout this journey.

Their contributions, directly or indirectly, have been an important part of bringing this project to completion.

**Built through collaboration, strengthened by mentorship, and driven by a shared passion for learning and innovation.**


# 🎙️ SkillTracker AI: AI Interview System for Skill Tracking (v4)

Mock interviews powered by generative AI with a **talking avatar interviewer**, **camera + microphone answers that are
recorded and stored**, **admin review of every recording**, **user accounts and roles**, a **database layer**, an
**example dataset** and an interactive **progress dashboard**.

**Stack:** Python · Streamlit · Google Gemini API (free) · SpeechRecognition · gTTS · SQLAlchemy (SQLite / PostgreSQL) · Plotly

## ✅ Free API requirements

| Service | Used for | Cost | Key needed? |
|---|---|---|---|
| **Google Gemini API** (AI Studio) | Question generation, answer scoring, feedback | **Free tier**, no credit card | **Yes**: https://aistudio.google.com/apikey |
| Google Web Speech (via `SpeechRecognition`) | Speech → text | Free | No |
| Google Translate TTS (via `gTTS`) | Reads questions aloud | Free | No |
| SQLite (default DB) | Storage | Free, built in | No |
| PostgreSQL (optional) | Storage for multi-server use | Your own server / free hosted tier | Connection URL |

- The Gemini free tier has **rate limits** that change over time (https://ai.google.dev/gemini-api/docs/rate-limits). A 5-question interview uses about 11 requests. With several users sharing one key, they share the same quota.
- Free-tier prompts may be used by Google to improve products. Don't speak confidential information.
- **No key? Still works:** the app falls back to the offline question bank with keyword scoring.
- Speech recognition and spoken questions need internet.

## ✨ New in v4: modern UI, dark mode and proctoring

**Dark / light toggle.** A 🌙 *Dark mode* switch sits at the top of the sidebar (and on the login page). The choice is
kept while you move between pages and after you sign out. It is applied with CSS on top of a light base theme, and the
Plotly charts, tables and alerts follow it.

**Redesigned interface.** Gradient hero headers, a 4-step progress bar (Choose skill, Configure, Interview, Report),
clickable skill cards showing your current level, status chips (skill, difficulty, question number, violations),
a two-column login page, card-style metrics, consistent buttons with hover and focus states, and a layout that
adapts to small screens.

**Window violations (proctoring).** During an interview, leaving the interview window counts as a violation:
switching to another tab, minimising the browser, or clicking into another window or application. One away-episode
counts once (tab hidden plus focus lost is a single violation).

- A warning banner appears immediately (*Violation 1 of 3 …*) and a chip shows the running count.
- At **3 violations the interview ends automatically**. It is saved and flagged, is **not scored**, does not change the skill
  level, and is excluded from trends and the leaderboard. The answers given so far are kept.
- The candidate must tick a rules checkbox before starting. Administrators see every violation in **Admin → Proctoring**
  (charts, log, CSV export); candidates see their terminated attempts in **Dashboard → History**.
- Configure with `PROCTORING_ENABLED` (1/0) and `MAX_VIOLATIONS` (default 3) in `.env`. Works in both Avatar and Classic mode.
- Existing databases are upgraded automatically (two columns and one table are added; no data is lost).

What proctoring can and cannot do: it detects tab switches, minimised windows and lost window focus from inside the
browser. It cannot see a second monitor, a phone, another person, or a determined user who disables scripts, and it is
not a replacement for human invigilation. The first ~6 s after a page load, and the camera/microphone permission
prompt, are ignored to avoid false alarms.

## 🧑‍💼 Avatar video interview (v3)

Choose **Avatar video interview** on the home page and tick the consent box. You then enter a "video call" room:

1. **Aria**, an animated human interviewer, greets you and asks the question **out loud**. Her mouth moves in time with
   the speech, she blinks, nods and looks at you.
2. When she finishes, the room switches to **your turn**: your camera shows as a small self-view, a recording timer runs
   and **live captions** of what you say appear.
3. You just talk. When you **pause for ~3.5 s** the answer ends automatically (or press **Done answering**).
4. Aria says "Thanks, that covers the main idea…" (a reaction based on your score, plus the AI's first feedback
   sentence when Gemini is online) and asks the next question. If she couldn't hear you she politely asks again.
5. After the last question click **View my report**.

**Recordings:** every answer is saved as a video file and a separate audio file under `storage/recordings/user_<id>/interview_<id>/`,
with the transcript, duration and score in the `recordings` table. Candidates can replay their own answers in
**Dashboard → History**. **Administrators** open **Admin → Recordings** to filter by candidate/skill, search transcripts,
play the video or audio, download, delete, and delete everything older than N days.

How it works (all free, no extra API key): the avatar is an animated SVG; speech uses the browser's built-in
text-to-speech; recording uses `MediaRecorder`; live captions use the browser's speech recognition. If the browser has no
speech recognition (e.g. Firefox), the server transcribes the audio with **ffmpeg** + free Google Web Speech
(install ffmpeg: `sudo apt install ffmpeg` / `brew install ffmpeg`). Typing an answer is always available.

| Browser | Avatar voice + recording | Live captions |
|---|---|---|
| Chrome / Edge (desktop, Android) | ✅ | ✅ |
| Safari | ✅ (mp4 recording) | partial |
| Firefox | ✅ | ❌ → ffmpeg server fallback |

Notes
- The avatar is a **2D animated illustration**, not a photorealistic video person. Photoreal talking heads (D-ID, HeyGen,
  Synthesia) are paid services; the component can be swapped for one later.
- Camera/microphone need **`localhost` or HTTPS**. Answers are capped at 2 minutes (`MAX_ANSWER_SECONDS`).
- **Privacy:** recordings are personal data. Keep the consent step, restrict admin accounts, use the retention tool, and
  back up/encrypt `storage/` in production. On hosts with an ephemeral disk (e.g. Streamlit Community Cloud) files are lost
  on restart: point `STORAGE_DIR` at a persistent volume or replace `core/storage.py` with an S3/GCS version.
- Typical size is ~5 MB per minute of video (about 0.5 MB for the audio track).

## 🔐 Accounts and roles

| Account | Password | Role |
|---|---|---|
| `admin` | `Admin@123` | Admin: all dashboards, cohort analytics, user management, database tools |
| `alice`, `bob`, `carol`, `dave`, `eve` | `Demo@123` | Candidates with pre-loaded interview history |

- Anyone can **create an account** on the login page (candidate role). Each candidate sees only their own history, plus the shared leaderboard.
- Passwords are stored as salted PBKDF2-SHA256 hashes (200k iterations). Logins lock for 30 s after 5 failures.
- **Change the admin password** (sidebar → Change password, or `ADMIN_PASSWORD` in `.env` before first run) and set `SHOW_DEMO_HINT=0` for any real deployment.
- Sessions live in the browser tab: refreshing the page logs you out.

## 🚀 Setup

```bash
cd ai_interview_skill_tracker
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env  → add GEMINI_API_KEY
streamlit run app.py
```
Open http://localhost:8501 and sign in. On the **first run** the app creates the database, the admin account
and loads the example dataset automatically (`AUTO_LOAD_SAMPLE=1`). Set it to `0` for a clean start.

Manual data commands:
```bash
python -m scripts.load_sample_data         # (re)load example users + history, safe to repeat
python -m scripts.generate_sample_dataset  # regenerate the CSVs with new random data
python -m pytest -q                        # run tests
```

## 🗄️ Database connectivity

Default: SQLite file `data/skilltracker.db`, no setup. To use PostgreSQL:
```bash
pip install psycopg2-binary
# .env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/skilltracker
```
Tables are created automatically. **Admin → Database** shows connection status and latency, row counts, a
SQLite backup download, and a "test another URL" tool to check a connection before switching.
(The SQLite path is fully tested; PostgreSQL uses portable SQL but has not been tested in this build.)

## 📁 Structure

```
ai_interview_skill_tracker/
├── app.py                       # Home + interview (classic mode and avatar room)
├── config.py                    # Settings, weights, accounts, DATABASE_URL
├── requirements.txt · .env.example · .streamlit/config.toml
├── core/
│   ├── ai_engine.py             # Gemini calls + offline fallback
│   ├── auth.py                  # Hashing, register/login UI, roles
│   ├── database.py              # SQLAlchemy layer (SQLite/PostgreSQL)
│   ├── dataset.py               # CSV import (sample or your own)
│   ├── theme.py                 # Light/dark tokens, CSS, toggle, themed charts
│   ├── proctor.py               # Python wrapper for the window-violation detector
│   ├── avatar_room.py           # Python wrapper for the avatar/camera component
│   ├── conversation.py          # Human-like lines: greeting, reactions, retries
│   ├── storage.py · recordings.py  # Save/read/delete audio-video files + metadata
│   ├── scoring.py · speech.py · charts.py · ui.py
├── components/interview_room/index.html   # Talking SVG avatar, camera/mic recorder, live captions (no build step)
├── components/proctor/index.html          # Invisible tab/window-violation detector
├── pages/
│   ├── 1_Dashboard.py           # Overview, Skills, History, Leaderboard, Cohort (admin)
│   └── 2_Admin.py               # Users, Recordings, Proctoring, Database, Datasets (admin only)
├── data/
│   ├── question_bank.json       # 30 offline questions
│   └── sample_dataset/          # users.csv, interviews.csv, answers.csv
├── scripts/                     # generate_sample_dataset.py, load_sample_data.py
├── storage/recordings/          # Created automatically: saved answer videos/audio
├── tests/                       # 23 tests (incl. simulated avatar interview, violations, theme, DB upgrade)
└── docs/SRS.md
```

## 🎛️ What's interactive
Skill pills · difficulty selector · "practise my weakest skill" shortcut · hints · live score chart during
the interview · score gauges and rubric bars · confetti for 80+ scores · downloadable report · dashboard
filters (skill/date) · moving-average toggle · skill deep-dive · admin "view dashboard as user".

## 🩹 Troubleshooting
| Problem | Fix |
|---|---|
| "Offline mode" in sidebar | Missing/invalid `GEMINI_API_KEY`; restart after editing `.env` |
| Mic widget missing | `pip install -U streamlit` (≥ 1.40); allow mic permission; use `localhost` or HTTPS |
| "Could not access camera/microphone" | Click the lock icon in the address bar → allow camera & mic; use `localhost`/HTTPS; or switch to Classic mode |
| Violation counted by mistake | Click only inside the interview page; avoid opening devtools or other windows. Raise `PROCTOR_GRACE_MS`, or set `PROCTORING_ENABLED=0` for practice |
| Dark mode looks off on a table | Tables use a colour-filter; toggle the theme again or report which widget |
| Avatar is silent | Browser has no speech voices or blocked audio; check system volume. The caption still shows the question |
| No live captions | Use Chrome/Edge, or install ffmpeg so the server can transcribe |
| Cannot connect to database | Check `DATABASE_URL`; for PostgreSQL install `psycopg2-binary` |
| 429 / quota errors | Free-tier limit; wait or set `GEMINI_MODEL=gemini-2.5-flash-lite`. App falls back automatically |
| Upgrading from v1 | v2 uses a new DB file (`skilltracker.db`); the old `interview.db` is ignored |

## ✅ What was verified
v4: violation counting, the automatic end at 3 (both modes), exclusion from scores and rankings, the admin
Proctoring tab, the theme switch, theme persistence after logout and the old-database upgrade are covered by tests.
The CSS dark theme and the real tab-switch detection were not viewed in a live browser here, so check them once in Chrome.

Unit tests plus a simulated avatar interview (fake browser answers using a real video file) confirm: turn-taking,
retry/skip when nothing is heard, files saved to disk, database rows, admin playback page, and access control. The
browser-only parts (camera permission, speech voices, live captions, auto-stop on silence) are implemented and
syntax-checked but need to be tried in your own browser.

## ⚖️ Limitations
Scores are AI-generated estimates for practice and self-tracking, not certified assessments.
