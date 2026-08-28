# AI Project Management Platform

Upload a project document → AI extracts a structured project entry → you review and
edit → export to PDF/DOCX. Multi-user, dark-themed, two swappable AI providers
(Gemini and local Ollama). Includes **Jarvis**, an agentic chatbot that answers questions
about your own project portfolio, analyzes cross-project technology patterns, and
recommends real, well-maintained GitHub repositories — plus an optional CV-style
Profile page.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI (async), SQLAlchemy 2.0 (async) + Alembic, PostgreSQL |
| Frontend | Next.js 16 (App Router, TS), Tailwind CSS v4, shadcn/ui (Base UI), Tiptap |
| Job queue | [SAQ](https://github.com/tobymao/saq) on the **Postgres** backend — no Redis needed on Windows dev |
| AI providers | Google Gemini and local Ollama, orchestrated via **LangChain** (`langchain-google-genai`, `langchain-ollama`); the rewrite path runs through a **LangGraph** `StateGraph` (`app/agents/rewrite_graph.py`), and Jarvis runs through a second, tool-calling LangGraph agent (`app/agents/chatbot_graph.py`). **Billing required on Gemini** — see below |
| Agent persona | Per-user "Business Analyst" (default) or "Technical Developer" system-prompt persona, configurable in Settings > AI Providers — swaps how extraction and "Enhance with AI" write the same facts, never what they invent |
| Jarvis (chatbot) | Real LLM tool-calling agent (`project_search`, `portfolio_analysis`, `github_search`) with a persisted, streamed (SSE) chat, floating bottom-right on every authenticated page. Grounds anything about the user's own projects in tool results only — never invents them — and separately can use general knowledge + a live GitHub search for technology recommendations. Configurable per-user provider (Gemini/Ollama) and a "preemptive suggestions" toggle in Settings > Chatbot. See `docs/RESEARCH.md` §E for live-verified findings (incl. Ollama tool-calling) |
| Profile page | Optional CV-style profile (`/profile`): photo, name, designation/team/organization, skills, speciality, and five AI-enhanced bio sections (Professional Biography, Work Experience Summary, Career Objective, Key Strengths, Responsibilities). Entirely optional — Jarvis works fully without it, and only uses filled-in fields as soft context for GitHub recommendations, never as a verified fact or in its greeting |
| Document parsing | `pdfplumber`, `docx2python`, `python-docx`, `mammoth` |
| Export | `html-for-docx` (DOCX), Playwright/Chromium (PDF) |
| Auth | JWT access + refresh tokens issued by FastAPI; Next.js BFF stores them as httpOnly cookies (browser never sees a token). Registration requires a first name (used for Jarvis's greeting) |

See `frontend/DESIGN.md` and `backend/DESIGN.md` for the full architecture writeups,
and `docs/RESEARCH.md` for the verified (Aug 2026) integration facts behind the
library choices below. **Read the "must act on" list in RESEARCH.md before shipping** —
it covers a Gemini API key deadline landing this month.

## Repo layout

```
backend/    FastAPI service — app/, alembic/, tests/
frontend/   Next.js app — app/, components/, hooks/, lib/
docs/       RESEARCH.md (provider/library facts), architecture notes
docker-compose.yml   Postgres for local dev
```

## Key decisions worth knowing before you touch this code

1. **Gemini gets PDFs directly** (Files API / inline bytes) instead of relying only on
   local text extraction — project documents are often layout-heavy (columns, tables,
   scans) and Gemini's document vision handles that far better than any Python PDF
   parser. Local extraction
   still runs, both as the Ollama provider's only input and as a pre-flight check
   ("0 chars extracted → this is a scan, refuse or force Gemini").
2. **Ollama Cloud cannot do structured output** (confirmed in Ollama's own docs as of
   Aug 2026). The Ollama provider is **local-only** for the extraction feature. Don't
   wire a cloud extraction path — it would silently misbehave.
3. **`.doc` (legacy binary) is rejected at upload**, not parsed. LibreOffice headless is
   the only thing that actually converts it on Windows and it's a 700MB dependency for
   a 19-year-obsolete format. Users get a clear "save as .docx or PDF" error instead.
4. **Ollama's default context window is 4096 tokens** and silently truncates longer
   documents server-side with a 200 OK. Every Ollama call sets `num_ctx` explicitly and
   verifies `prompt_eval_count` after the call. We use the native `ollama` client, never
   the OpenAI-compatible `/v1` shim (which has no way to set `num_ctx` at all).
5. **Gemini API keys**: standard (unrestricted) keys are being phased out — rejected
   entirely from **September 2026**. Settings UI must guide users to create an "auth
   key" in AI Studio, and the "Test connection" error copy needs to say so on a 403.
6. **PDF export uses Playwright/Chromium, not WeasyPrint** — WeasyPrint still requires
   an MSYS2 + Pango native install on Windows as of v69 (2026), which is a real
   onboarding blocker for a Windows-first dev team. `render/pdf.py` is written behind a
   `PdfRenderer` protocol so WeasyPrint can be swapped in as a lighter Linux-prod
   backend later without touching call sites.
7. **AI never overwrites hand-written prose silently.** Extraction only fills fields the
   user hasn't touched (`keepDirtyValues` semantics); the per-field "Enhance"/"Generate
   from long" buttons return a suggestion into a review panel that requires an explicit
   Accept. See `frontend/DESIGN.md` §4.4 — this is the most important UX rule in the app.
8. **Jarvis is grounded-first, not a generic chat assistant.** Its system prompt
   (`app/providers/prompts.py`) draws a hard line: any claim about the user's own
   projects must come from a `project_search`/`portfolio_analysis` tool call in that
   conversation, never invented; only genuinely general technology questions may use the
   model's own knowledge, grounded further by a live `github_search` call rather than a
   possibly-stale remembered repo. The "preemptive suggestions" Settings toggle changes
   *whether Jarvis may volunteer* a GitHub suggestion unprompted — it never changes
   *what's allowed to be true* in an answer.
9. **The GitHub search tool uses a real quality bar, not just a keyword match** —
   minimum stars, `archived:false`, and a rolling freshness window (`pushed:>=`), all
   configurable via `GITHUB_MIN_STARS`/`GITHUB_FRESHNESS_MONTHS` — so recommendations are
   real, current, and not dead forks. See `docs/RESEARCH.md` §E for the live-tested
   results (incl. confirming Ollama's `gemma4:e2b`/`e4b` do real tool-calling, not just
   narrated text).

## Getting started

### 1. Postgres — pick one

**Docker** (needs Docker Desktop running):
```bash
docker compose up -d db
```
Maps to host port **5433**, not 5432 — deliberately, so it doesn't collide with a native
Postgres install some dev machines already have running. Set
`DATABASE_URL=postgresql+asyncpg://aipm:aipm@localhost:5433/aipm` in `backend/.env`.

**Native install** (no Docker): create the role/db once —
```powershell
& "C:\Program Files\PostgreSQL\<version>\bin\psql.exe" -U postgres -c "CREATE ROLE aipm WITH LOGIN PASSWORD 'aipm'; CREATE DATABASE aipm OWNER aipm;"
```
and use port **5432** in `DATABASE_URL` (the default in `.env.example`).

### 2. Backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env        # fill in SECRET_KEY, FERNET_KEY, DATABASE_URL (port per above)
                               # GITHUB_TOKEN is optional (Jarvis's github_search tool
                               # works unauthenticated too, just rate-limited harder)
alembic upgrade head
uvicorn app.main:app --port 8000
```

> **No `--reload` on Windows.** Uvicorn's `--reload` runs the app in a subprocess and, to do
> that safely, forces Python's `SelectorEventLoop` instead of `ProactorEventLoop`
> (`use_subprocess=True` → `uvicorn/loops/asyncio.py`). `SelectorEventLoop` can't launch
> subprocesses on Windows at all, and Playwright's `async_playwright().start()` in
> `app/main.py`'s `lifespan()` launches its driver as a subprocess — so with `--reload` the
> app crashes on startup with `NotImplementedError`. Restart uvicorn manually after code
> changes instead.

### 3. Worker — starts automatically, no separate terminal needed

`uvicorn`'s startup (`app/main.py`'s `lifespan()`) auto-spawns
`saq app.workers.settings.settings` as a child process, so document uploads get
processed without anything else running. Only start it manually if you want SAQ's
built-in dashboard:
```bash
saq app.workers.settings.settings --web    # web UI at :8080 — optional, safe to run
                                            # alongside the auto-started one
```

### 4. Frontend (separate terminal)
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev                    # http://localhost:3000
```

## Status

Backend: domain models, auth, provider abstraction (Gemini + Ollama via LangChain, with
the rewrite path orchestrated through a one-node LangGraph `StateGraph`), a per-user
Agent Persona setting (Business Analyst / Technical Developer, swapping the system
prompt for both extraction and rewrite), document ingest, DOCX/PDF export, and job queue
wiring are in place per the design docs.

Frontend: app shell, routing, API client config, and the full Add/Edit Project form are
built, including the Tiptap dual rich-text editor (long/short pairs, toolbar, live char
counters, paste-overflow guard) for both Description and Responsibilities. Each editor box
has an "Enhance with AI" icon button in its own toolbar (the short box also gets "Generate
from long"), grounded with the project's name/role/technologies as context; results land
in an accept/discard suggestion panel — never a silent overwrite — and an animated
gradient ring (Gemini-style) marks a box while AI is writing into it or just after a
suggestion is accepted. Try it without a backend running at `/styleguide/editor`.

Not yet built: the document upload → AI extraction job-polling flow (drag-and-drop, stage
stepper, auto-filling the form from a parsed document) and the resulting AI-provenance
tracking (which fields were AI-filled vs hand-typed, revert-to-original) — see
`frontend/DESIGN.md` §9 milestones M6–M7.

**Jarvis (chatbot) — built and live-tested end to end**, backend and frontend: a
per-request-built LangGraph agent (`app/agents/chatbot_graph.py`) with three tools
(`app/agents/chat_tools.py`), streamed to the browser over SSE
(`app/routers/chat.py` → `frontend/lib/chat.ts` → `frontend/components/chat/`), with
full history persistence (`chat_sessions`/`chat_messages`) so a reload resumes the same
conversation without repeating the greeting. Verified live against a real local Ollama
model (`gemma4:e2b`) and the real GitHub Search API — see `docs/RESEARCH.md` §E. Settings
> Chatbot lets a user pick Jarvis's provider and toggle preemptive GitHub suggestions.

**Profile page — built**: `/profile` (`frontend/app/(app)/profile/`, backend
`app/routers/profile.py`), entirely optional CV-style content with the same
propose-then-accept "Enhance with AI" pattern as the project form, adapted for its plain
(non-rich-text) bio fields.
