# AI Project Management Platform

Upload a project document → AI extracts a structured project entry → you review and
edit → export to PDF/DOCX. Multi-user, dark-themed, two swappable AI providers
(Gemini and OpenAI). Includes **Jarvis**, an agentic chatbot that answers questions
about your own project portfolio, analyzes cross-project technology patterns, and
recommends real, well-maintained GitHub repositories — plus an optional CV-style
Profile page.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI (async), SQLAlchemy 2.0 (async) + Alembic, PostgreSQL |
| Frontend | Next.js 16 (App Router, TS), Tailwind CSS v4, shadcn/ui (Base UI), Tiptap |
| Job queue | [SAQ](https://github.com/tobymao/saq) on the **Postgres** backend — no Redis needed on Windows dev |
| AI providers | Google Gemini and OpenAI, orchestrated via **LangChain** (`langchain-google-genai`, `langchain-openai`); the rewrite path runs through a **LangGraph** `StateGraph` (`app/agents/rewrite_graph.py`), and Jarvis runs through a second, tool-calling LangGraph agent (`app/agents/chatbot_graph.py`). **Billing required on both providers** — see below |
| Agent persona | Per-user "Business Analyst" (default) or "Technical Developer" system-prompt persona, configurable in Settings > AI Providers — swaps how extraction and "Enhance with AI" write the same facts, never what they invent |
| Jarvis (chatbot) | Real LLM tool-calling agent (`project_search`, `portfolio_analysis`, `github_search`) with a persisted, streamed (SSE) chat, floating bottom-right on every authenticated page. Grounds anything about the user's own projects in tool results only — never invents them — and separately can use general knowledge + a live GitHub search for technology recommendations, never repeating a repo already suggested to that user. Configurable per-user provider (Gemini/OpenAI) and a "preemptive suggestions" toggle in Settings > Chatbot. Conversations are managed from a dedicated `/conversations` page (search, star, delete, resume), get an auto-generated title after the first exchange, and are summarized in the background once they get long, to keep replayed context bounded. See `docs/RESEARCH.md` §E for live-verified findings from when this was built against Gemini and a local Ollama model — the app itself no longer uses Ollama |
| Proactive suggestions | A SAQ background job — triggered whenever a project's technologies change, and on a 20-minute catch-up cron otherwise — computes each user's most-used technologies and looks up real GitHub repos for them, shown as a "Suggested for you" card on the Dashboard, independent of whether the user ever opens the chat. Shares the same no-repeat guarantee and quality bar (stars/freshness/not-archived) as Jarvis's own `github_search`, and is gated by the same Settings > Chatbot "preemptive suggestions" toggle |
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

1. **Both providers get PDFs directly** (Gemini via Files API/inline bytes, OpenAI via a
   base64 file content block) instead of relying only on local text extraction — project
   documents are often layout-heavy (columns, tables, scans) and document vision handles
   that far better than any Python PDF parser. Local extraction still runs as a pre-flight
   check ("0 chars extracted → this is a scan") and as the fallback for DOCX/TXT.
2. **`.doc` (legacy binary) is rejected at upload**, not parsed. LibreOffice headless is
   the only thing that actually converts it on Windows and it's a 700MB dependency for
   a 19-year-obsolete format. Users get a clear "save as .docx or PDF" error instead.
3. **Structured output is bound directly on both providers** rather than via LangChain's
   `.with_structured_output()` — Gemini's `response_mime_type`/`response_json_schema`,
   OpenAI's `response_format` json_schema — to keep the exact request shape explicit and
   stable across `langchain-google-genai`/`langchain-openai` versions. Both providers also
   check `finish_reason` explicitly (`MAX_TOKENS`/`length`), since a token-cap truncation
   otherwise comes back as a normal response with no exception.
4. **Gemini API keys**: standard (unrestricted) keys are being phased out — rejected
   entirely from **September 2026**. `providers/gemini.py`'s `test_connection()` already
   detects a `PROVIDER_AUTH` failure and returns copy pointing users to create a new key
   at aistudio.google.com/api-keys; Settings renders that message verbatim on a failed test.
5. **PDF export uses Playwright/Chromium, not WeasyPrint** — WeasyPrint still requires
   an MSYS2 + Pango native install on Windows as of v69 (2026), which is a real
   onboarding blocker for a Windows-first dev team. `render/pdf.py` is written behind a
   `PdfRenderer` protocol so WeasyPrint can be swapped in as a lighter Linux-prod
   backend later without touching call sites.
6. **AI never overwrites hand-written prose silently.** Extraction only fills fields the
   user hasn't touched (`keepDirtyValues` semantics); the per-field "Enhance"/"Generate
   from long" buttons return a suggestion into a review panel that requires an explicit
   Accept. See `frontend/DESIGN.md` §4.4 — this is the most important UX rule in the app.
7. **Jarvis is grounded-first, not a generic chat assistant.** Its system prompt
   (`app/providers/prompts.py`) draws a hard line: any claim about the user's own
   projects must come from a `project_search`/`portfolio_analysis` tool call in that
   conversation, never invented; only genuinely general technology questions may use the
   model's own knowledge, grounded further by a live `github_search` call rather than a
   possibly-stale remembered repo. The "preemptive suggestions" Settings toggle changes
   *whether Jarvis may volunteer* a GitHub suggestion unprompted — it never changes
   *what's allowed to be true* in an answer.
8. **The GitHub search tool uses a real quality bar, not just a keyword match** —
   minimum stars, `archived:false`, and a rolling freshness window (`pushed:>=`), all
   configurable via `GITHUB_MIN_STARS`/`GITHUB_FRESHNESS_MONTHS` — so recommendations are
   real, current, and not dead forks. See `docs/RESEARCH.md` §E for the live-tested
   results from when this was verified against Gemini and a local Ollama model.
9. **Tasks stay solo/single-user, not multi-tenant.** No organizations, teams, roles, or
   assignees — every task is `user_id`-scoped exactly like projects, and ownership is
   checked through one shared seam (`core/ownership.require_owned`) rather than the four
   ad-hoc variants that existed before this feature. Adding real multi-tenancy later is a
   deliberate, separate, multi-week decision — not a gap in this feature.
10. **AI work breakdown repairs malformed model output instead of failing the job.**
    `services/breakdown_service.normalize_breakdown()` is total: an unknown `parent_ref`,
    a duplicate ref, a 3+ level parent chain, an over-length title, or a `grounded=true`
    task with no supporting quote are all fixed in place with a note recorded, never
    raised. A job failing because the model got one field wrong is a worse outcome for the
    user than a job that says "I fixed 2 things."
11. **Every proposed task's provenance is enforced by the UI, not just the prompt.** A
    task can only render as "grounded" if the model also supplied a verbatim quote from
    the source document; `grounded: false` suggestions are visually separated ("Suggested
    additions — not in your document") and never pre-selected. The prompt asks the model
    to behave this way, but the review screen — not the prompt — is what actually
    guarantees a user never accepts an invented fact without seeing it flagged as one.
12. **`breakdown_jobs` is its own table, not a `kind` column on `extraction_jobs`.** The
    existing extraction poll endpoint hard-codes its result shape and has the inverse
    nullability from what a breakdown needs: extraction requires a document and treats
    the project as optional, while a breakdown requires the project and treats the
    document as optional (a prompt-only breakdown has no document at all). It reuses the
    *same* `job_status` Postgres enum, though, so the 4-stage stepper, cancel endpoint,
    and stale-job reaper all work unchanged for both job types.

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

Backend: domain models, auth, provider abstraction (Gemini + OpenAI via LangChain, with
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
conversation without repeating the greeting. Originally verified live against Gemini, a
local Ollama model, and the real GitHub Search API — see `docs/RESEARCH.md` §E; the app
itself has since moved from Ollama to OpenAI as its second provider. Settings
> Chatbot lets a user pick Jarvis's provider and toggle preemptive GitHub suggestions.

**Conversation management — built**: sessions can be starred, searched by title, sorted,
and deleted from a new `/conversations` page (`frontend/app/(app)/conversations/`,
`frontend/components/conversations/`); resuming a conversation from that page reopens the
floating widget on it via a new `ChatWidgetProvider`
(`frontend/components/chat/chat-widget-context.tsx`) shared through `AppShell`. A session's
title is now generated automatically from its first exchange (`generate_session_title`,
replacing the old first-60-chars behavior), and long conversations are compacted in the
background (`compact_history`, both SAQ jobs in `app/services/chat_service.py`) — older
turns get folded into a running summary once a session passes 50 unreplayed messages, so
what's sent to the LLM each turn stays bounded without deleting anything from the visible
history.

**Proactive GitHub repo suggestions — built**: a SAQ background job
(`app/services/suggestion_service.py`) computes each user's top technologies
(`app/services/portfolio_service.py`) and looks up real repos for them
(`app/services/github_service.py`, cached cross-user in `github_repo_cache` via
`app/services/github_cache_service.py` to stay well under GitHub's rate limit), storing
results in `repo_suggestions` and surfacing them as a dismissable "Suggested for you" card
on the Dashboard (`frontend/components/dashboard/suggested-repos-card.tsx`). Triggered
both on project edits (`app/routers/projects.py`) and a 20-minute catch-up cron
(`app/workers/suggestion_refresh.py`). Shares one no-repeat record with Jarvis's own live
`github_search` tool, so a repo already suggested to a user — via chat or the dashboard —
is never suggested to them again.

**Profile page — built**: `/profile` (`frontend/app/(app)/profile/`, backend
`app/routers/profile.py`), entirely optional CV-style content with the same
propose-then-accept "Enhance with AI" pattern as the project form, adapted for its plain
(non-rich-text) bio fields, including an optional free-text instruction prompt before
generating a suggestion.
