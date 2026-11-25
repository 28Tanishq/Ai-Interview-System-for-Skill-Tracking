# Software Requirements Specification (SRS)
## AI Interview System for Skill Tracking
Version 4.0 · Format follows IEEE 830 / ISO 29148 (condensed)

---

## 1. Introduction

### 1.1 Purpose
This document specifies the requirements for the **AI Interview System for Skill Tracking**, a web application
that conducts voice-based mock technical interviews using a generative AI model, scores each answer against a
rubric, and tracks skill progress over time.

### 1.2 Scope
The system lets a candidate choose a skill, answer dynamically generated questions by speaking, receive
instant AI feedback and scores, and view long-term progress on a dashboard. It is a single-user-per-session,
locally hosted Streamlit application with an embedded SQLite database. It is intended for self-practice,
training institutes and early-stage skill assessment, not for high-stakes hiring decisions.

### 1.3 Definitions
| Term | Meaning |
|---|---|
| STT | Speech-to-text (speech recognition) |
| TTS | Text-to-speech |
| Rubric | 4 criteria scored 0-10: accuracy, depth, clarity, relevance |
| Proficiency | Exponential moving average (0-100) of a user's interview scores per skill |
| Gemini | Google's generative AI model accessed through the Gemini API (free tier) |

### 1.4 References
Streamlit docs, Google Gen AI SDK (`google-genai`), SpeechRecognition library, gTTS, SQLite.

### 1.5 Overview
Section 2 describes the product, Section 3 the specific requirements, Section 4 the data model, Section 5 the
scoring model, Section 6 acceptance criteria.

---

## 2. Overall Description

### 2.1 Product perspective
Standalone Python application with account-based access. External services: Gemini API (generation/evaluation), Google Web Speech
endpoint via SpeechRecognition (STT), Google Translate TTS via gTTS (spoken questions).

```
 Browser (mic + speaker)
        │  audio / text
 ┌──────▼──────────────────────────────┐
 │ Streamlit UI (app.py, pages/)       │
 ├─────────────┬───────────────────────┤
 │ core/speech │ core/ai_engine ──────────► Gemini API (free tier)
 │ (STT, TTS)  │ core/scoring          │   └─ offline fallback (question bank)
 ├─────────────┴───────────────────────┤
 │ core/database  ─► SQLite (data/interview.db)
 └─────────────────────────────────────┘
```

### 2.2 User classes
| Class | Description |
|---|---|
| Candidate | Registers, signs in, takes interviews, views own dashboard and the leaderboard |
| Administrator | Everything a candidate can do, plus: view any user's dashboard, cohort analytics, manage users (create, role, activate, reset password, delete), inspect/test the database, import/export datasets |

### 2.3 Operating environment
Python 3.10+, Windows/macOS/Linux, modern browser (Chrome, Edge, Firefox, Safari) with microphone permission,
internet connection for AI, STT and TTS.

### 2.4 Constraints
- Free-tier Gemini API has rate limits and may use submitted data to improve Google products (see Google's terms); do not submit confidential data.
- Google Web Speech endpoint is intended for short clips and offers no SLA.
- Browser microphone access requires `localhost` or HTTPS.

### 2.5 Assumptions
User has a working microphone, speaks the selected language, and can obtain a free API key.

---

## 3. Specific Requirements

### 3.1 Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | The system shall provide account registration and sign-in with username and password; each user has a separate profile and history. | Must |
| FR-02 | The system shall let the user select a skill from a predefined list or enter a custom skill. | Must |
| FR-03 | The system shall let the user select starting difficulty (Beginner/Intermediate/Advanced) and 3-10 questions. | Must |
| FR-04 | The system shall generate each question dynamically with the generative AI model, avoiding repeats within the interview. | Must |
| FR-05 | The system shall adapt difficulty up or down based on the score of the previous answer (≥80 harder, <40 easier). | Should |
| FR-06 | The system shall optionally read each question aloud (TTS). | Should |
| FR-07 | The system shall capture the candidate's spoken answer through the browser microphone. | Must |
| FR-08 | The system shall convert speech to text and display an editable transcript. | Must |
| FR-09 | The system shall allow typed answers as a fallback when speech is unavailable. | Must |
| FR-10 | The system shall evaluate each answer with the AI model on four rubric criteria (0-10) and produce feedback, strengths, improvements and a model-answer hint. | Must |
| FR-11 | The system shall compute a weighted 0-100 score per answer and an interview score as the mean of answer scores. | Must |
| FR-12 | The system shall maintain a per-skill proficiency (EMA) and map it to a level (Beginner/Intermediate/Advanced/Expert). | Must |
| FR-13 | The system shall measure speaking metrics (word count, filler words) for each answer. | Should |
| FR-14 | The system shall generate an end-of-interview summary: assessment, strengths, focus areas, study resources. | Must |
| FR-15 | The system shall persist all interviews, answers, scores and proficiency in a database. | Must |
| FR-16 | The dashboard shall show KPIs, skill radar, proficiency table, score trend, rubric breakdown, speaking-habit trend, weakest questions and history with drill-down. | Must |
| FR-17 | The user shall be able to export answer history as CSV. | Should |
| FR-18 | The user shall be able to load demo data and delete all of their own data. | Should |
| FR-19 | If the AI API key is missing, rate-limited or failing, the system shall fall back to an offline question bank and keyword-based scoring without crashing. | Must |
| FR-20 | The user shall be able to skip a question (scored 0). | Could |
| FR-21 | Passwords shall be stored only as salted PBKDF2-SHA256 hashes; the password policy requires 8+ characters with letters and digits. | Must |
| FR-22 | The system shall support two roles (candidate, admin) and restrict admin pages and cross-user data to admins. | Must |
| FR-23 | The system shall lock sign-in for 30 seconds after 5 consecutive failures in a session. | Should |
| FR-24 | Multiple users shall be able to use the system concurrently, each with isolated interview state and data. | Must |
| FR-25 | Users shall be able to change their own password; admins shall be able to reset passwords, change roles, deactivate and delete users. | Must |
| FR-26 | The database shall be selected by a single `DATABASE_URL` (SQLite default; PostgreSQL supported) and tables shall be created automatically. | Must |
| FR-27 | The admin console shall display database connection status, latency, table row counts and allow testing another database URL. | Should |
| FR-28 | The system shall ship an example dataset (CSV) and load it on first run (configurable), and allow admins to load it again or import user-supplied CSVs without creating duplicates. | Must |
| FR-29 | A leaderboard shall rank candidates by average score overall and by skill proficiency. | Should |
| FR-30 | Admins shall see cohort analytics: active users, scores by skill, candidate × skill heat-map, weekly trend. | Should |
| FR-31 | The dashboard shall provide skill and date filters; users shall be able to download an interview report and export answers as CSV. | Should |
| FR-32 | The system shall offer an avatar interview mode in which an animated human interviewer speaks each question aloud with synchronised mouth movement, blinking and head motion. | Must |
| FR-33 | In avatar mode the system shall capture the candidate's answer through camera and microphone, show a self-view, a recording timer and live captions. | Must |
| FR-34 | The system shall run the interview as a conversation: automatic turn-taking, end-of-answer detection on a pause (default 3.5 s) with a manual "Done" control, a spoken reaction to each answer, and a polite re-ask if no speech is detected. | Must |
| FR-35 | The system shall require explicit consent before any camera/microphone recording starts. | Must |
| FR-36 | The system shall store each recorded answer (video file, separate audio file) in server storage and its metadata (user, interview, question, transcript, duration, size) in the database. | Must |
| FR-37 | Administrators shall be able to list, filter, search, play, download and delete all recordings and delete recordings older than a chosen age. | Must |
| FR-38 | Candidates shall be able to replay their own recordings; they shall not be able to access other users' recordings. | Must |
| FR-39 | If the browser lacks speech recognition, the system shall transcribe the recorded audio on the server; a typed-answer alternative shall always be available. | Should |
| FR-40 | Deleting a user or wiping data shall also delete the associated recording files. | Must |
| FR-41 | The system shall provide a light/dark theme switch on every page and on the login page; the choice shall persist across pages and sign-out and shall apply to charts, tables and alerts. | Must |
| FR-42 | During an interview the system shall detect window violations (tab switch, minimised window, loss of window focus) in the browser, count one violation per away-episode, and show an immediate warning. | Must |
| FR-43 | The system shall end the interview automatically when the violation count reaches the configured limit (default 3), mark it terminated, and exclude it from scores, proficiency, analytics and the leaderboard. | Must |
| FR-44 | Violations shall be stored with time, type and interview, and shall be viewable and exportable by administrators; candidates shall see their terminated attempts. | Must |
| FR-45 | The candidate shall acknowledge the interview rules, including the violation limit, before starting. | Must |
| FR-46 | The interface shall present a step indicator, skill cards showing proficiency, status chips and responsive layouts. | Should |
| FR-47 | Databases created by earlier versions shall be upgraded automatically without data loss. | Must |

### 3.2 External interface requirements
- **UI:** Streamlit multipage web app. Main page (interview) and Progress Dashboard page. Sidebar shows profile, AI status, speech settings.
- **Hardware:** microphone, speakers/headphones.
- **Software interfaces:** Gemini API over HTTPS (`google-genai` SDK, JSON response mode); Google Web Speech via `SpeechRecognition`; gTTS; SQLite via Python `sqlite3`.
- **Communication:** HTTPS outbound only; no inbound ports other than local Streamlit (default 8501).

### 3.3 Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Performance | Question generation and answer evaluation should complete within 10 s at the 90th percentile on a normal connection. |
| NFR-02 | Usability | A new user shall start an interview within 3 clicks of opening the app; all feedback uses plain language. |
| NFR-03 | Reliability | No unhandled exception shall reach the user on API/STT/TTS failure; graceful messages and fallbacks are shown. |
| NFR-04 | Security | API keys and the database URL are stored only in `.env` / environment. SQL uses bound parameters. Passwords are never stored or logged in clear text; database URLs are masked when displayed. |
| NFR-05 | Privacy | Audio is processed in memory and not stored; only transcripts are saved. Users can delete their data. |
| NFR-06 | Portability | Runs on Python 3.10+ across Windows, macOS, Linux without native audio drivers (no PyAudio required). |
| NFR-07 | Maintainability | Modular layers (UI / AI / scoring / data); scoring weights and levels configurable in `config.py`; unit tests for core logic. |
| NFR-08 | Cost | The complete system shall be operable at zero cost using free tiers. |
| NFR-09 | Accessibility | Every voice action has a typed alternative; transcript is editable. |
| NFR-10 | Scalability | Suitable for tens of concurrent users on SQLite; PostgreSQL recommended beyond that. The shared free Gemini quota is the main limit. |
| NFR-11 | Deployability | Zero-config first run (auto-created DB, admin account, sample data). |
| NFR-12 | Privacy | Recordings are personal data: collected only after consent, accessible only to the owner and administrators, deletable on demand or by retention policy, and never served from a public path (storage paths are validated against traversal). |
| NFR-13 | Compatibility | Avatar mode targets current Chrome/Edge; Safari and Firefox are supported with reduced live-caption capability. Camera/microphone require localhost or HTTPS. |
| NFR-15 | Fairness | Violation detection shall ignore the initial page load and camera/microphone permission prompts; a single absence shall count once. Proctoring is configurable and can be disabled. |
| NFR-16 | Usability | Both themes shall keep text contrast readable on all controls; motion shall be reduced when the user's system requests it. |
| NFR-14 | Capacity | Video is recorded at about 0.7 Mbit/s (about 5 MB per minute); answers are capped at 120 s. Storage must be sized accordingly. |

### 3.4 Use cases

**UC-1 Take an interview**
1. User opens app, enters name. 2. Selects skill, difficulty, question count and presses *Start*.
3. System generates and speaks question 1. 4. User records answer; system shows transcript.
5. User submits; system scores and shows feedback. 6. Steps 3-5 repeat. 7. System shows report and updates proficiency.
*Alternate:* STT fails → user types answer. AI fails → offline fallback (FR-19).

**UC-2 Review progress** — User opens the dashboard, reviews trends, drills into a session, exports CSV.

---

## 4. Data Requirements

```
users(id PK, username UNIQUE, full_name, email, password_hash, salt, role, is_active, created_at, last_login)
interviews(id PK, user_id FK, skill, difficulty, total_questions, started_at, finished_at,
           overall_score, summary, ai_mode)
answers(id PK, interview_id FK, q_no, question, answer, input_mode,
        accuracy, depth, clarity, relevance, overall, filler_count, word_count,
        feedback, strengths, improvements, created_at)
skill_proficiency(user_id FK, skill, proficiency, sessions, updated_at; PK(user_id, skill))
recordings(id PK, interview_id FK, user_id FK, q_no, question, transcript, video_path, audio_path,
           mime, duration_sec, size_bytes, created_at)   -- files live under STORAGE_DIR
```
Relationships: users 1-N interviews 1-N answers; users 1-N skill_proficiency. Deleting a user removes dependent rows in code (portable across SQLite and PostgreSQL).

---

## 5. Scoring Model

- Answer score = 10 × (0.40·accuracy + 0.25·depth + 0.20·clarity + 0.15·relevance), range 0-100.
- Interview score = arithmetic mean of its answer scores.
- Proficiency_new = (1 − α)·Proficiency_old + α·InterviewScore, α = 0.35 (first session sets the baseline).
- Levels: 0-39 Beginner, 40-59 Intermediate, 60-79 Advanced, 80-100 Expert.
- Filler rate = filler words / total words × 100.
- Offline scoring: accuracy = keyword coverage × 10; depth from word count and coverage; clarity from sentence count; relevance from coverage.

---

## 6. Acceptance Criteria

| # | Criterion | Verifies |
|---|---|---|
| AC-1 | With a valid key, 5 consecutive generated questions are distinct and on-topic. | FR-04 |
| AC-2 | Recording and stopping the mic fills the transcript within 5 s on a normal connection. | FR-07/08 |
| AC-3 | Submitting a strong answer yields a higher score than a vague answer to the same question. | FR-10/11 |
| AC-4 | Removing the API key still lets a full interview complete. | FR-19 |
| AC-5 | After two sessions in one skill, proficiency equals the EMA formula. | FR-12 |
| AC-6 | Dashboard renders all charts for demo data; CSV export opens in Excel. | FR-16/17 |
| AC-7 | `pytest` passes (23 tests). | NFR-07 |
| AC-8 | Wrong password is rejected; a candidate cannot open the Admin page; two users see only their own history. | FR-01/22/24 |
| AC-9 | First run with an empty database loads 5 demo users, ~69 interviews, ~345 answers; loading again adds nothing. | FR-28 |
| AC-11 | In avatar mode the interviewer speaks, the recorder starts automatically, the answer ends after a pause, and the next question follows without clicking. | FR-32/33/34 |
| AC-12 | After an avatar interview, each answer has a video and audio file on disk and a row in Admin → Recordings that plays back. | FR-36/37 |
| AC-13 | A candidate cannot open Admin → Recordings; deleting a user removes their files. | FR-38/40 |
| AC-14 | Three simulated violations end an interview automatically; the attempt is flagged, unscored and absent from analytics. | FR-42/43 |
| AC-15 | The theme switch changes the page colours, persists after sign-out and works on the dashboard and admin pages. | FR-41 |
| AC-10 | Admin → Database shows "Connected" with latency and row counts. | FR-26/27 |

---

## 7. Future Enhancements
Stronger proctoring (second-screen and face detection, screen-share checks), photorealistic talking-head avatar (D-ID/HeyGen), emotion analysis of recorded video, cloud object storage for recordings, persistent login cookies, email verification and password reset, OAuth sign-in, resume-based questions, trainer groups, PDF report export, Gemini
native audio input to analyse tone and pace, PostgreSQL backend.
