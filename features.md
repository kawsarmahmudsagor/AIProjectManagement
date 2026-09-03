# Features

This document explains every user-facing feature of the AI Project Management Platform: what it
does, how it works under the hood, and how to use it. The platform is **solo/single-user** — no
teams, organizations, or assignees — every project, task, and conversation belongs to exactly one
account. The golden rule that runs through every AI feature here: **AI never silently overwrites
your own writing.** Every AI output lands in a review step (a suggestion panel, an accept/dismiss
list) that requires an explicit action from you before it touches your data.

---

## Contents

1. [Account & Login](#1-account--login)
2. [Projects](#2-projects)
3. [Document Upload → AI Extraction](#3-document-upload--ai-extraction)
4. ["Enhance with AI" / "Generate from Long"](#4-enhance-with-ai--generate-from-long)
5. [Tasks](#5-tasks)
6. [AI Work Breakdown](#6-ai-work-breakdown)
7. [Project Export (PDF / DOCX)](#7-project-export-pdf--docx)
8. [Jarvis — the AI Chatbot](#8-jarvis--the-ai-chatbot)
9. [Conversations Page](#9-conversations-page)
10. [AI Provider Settings](#10-ai-provider-settings)
11. [Agent Persona](#11-agent-persona)
12. [Profile Page](#12-profile-page)
13. [Dashboard Suggestions](#13-dashboard-suggestions)
14. [GitHub Repo Suggestions](#14-github-repo-suggestions)
15. [Brag Document Generator](#15-brag-document-generator)

---

## 1. Account & Login

**What it is:** Email + password authentication. Your session is a JWT access/refresh token pair,
but you never see the token directly — the app's Next.js layer stores it as an httpOnly cookie.

**How to use it:** Register at `/register` with an email, password, and first name (first name is
required — everything else, including middle/last/preferred name, is optional and can be filled
in later on the [Profile page](#12-profile-page)). Log in at `/login`. Your session refreshes
automatically in the background; you're only asked to log in again if the refresh token itself
expires.

**Constraints:** Password 8–128 characters. First name 1–80 characters, required.

---

## 2. Projects

**What it is:** The core unit of your portfolio. Each project has a name, your role on it,
start/end dates (or "currently working on this"), a technologies list, an optional URL, and two
**dual rich-text sections**:

- **Description** — what the project is/does.
- **Responsibilities** — specifically what *you* did on it.

Each section has a long form (the full write-up) and a short form (a compact summary used in
lists and AI context). This Responsibilities field matters beyond just display — it's the exact
context the [Brag Document Generator](#15-brag-document-generator) uses to ground your monthly
report, especially useful when you only worked on *part* of a larger project.

**How to use it:** Go to `/projects` → **Add New Project** for a full-page form, or click into an
existing project to view/edit it. Each rich-text box (Description, Responsibilities) is a Tiptap
editor with bold/italic/underline and both list types, a live character counter, and its own
"Enhance with AI" button (see [§4](#4-enhance-with-ai--generate-from-long)).

**Under the hood:** `POST/GET/PATCH/DELETE /projects[/{id}]`. Rich text is stored as an HTML +
plain-text pair per field; the plain-text side is always recomputed from the HTML on save, so it's
never out of sync. Changing a project's technologies list triggers a background refresh of your
[GitHub suggestions](#14-github-repo-suggestions).

**Constraints:** Name 1–200 chars, role 1–120 chars. Short description/responsibilities: up to 390
characters. Long description/responsibilities: up to 10,000 characters. Up to 40 technologies. If
"currently working on this" is checked, the end date is cleared automatically.

---

## 3. Document Upload → AI Extraction

**What it is:** Instead of typing a new project by hand, upload a source document (a resume entry,
a statement of work, etc.) and let AI pre-fill the form for you. This never blocks manual entry,
and it never overwrites a field you've already typed into — it only fills in what's still empty.

**How to use it:** On the Add/Edit Project form, drag a file onto the upload area (or click to
browse). You'll see a progress stepper (queued → parsing → extracting → structuring) with a
cancel button. When it finishes, the form fills in automatically, and you're told exactly which
fields it couldn't find anything for.

**Under the hood:** `POST /documents` stores the file and kicks off a background job
(`ExtractionJob`). Both supported AI providers (Gemini and OpenAI) read PDFs directly as documents
rather than relying only on text extraction, since project documents are often layout-heavy
(columns, tables, scans). The extraction prompt is strict: *extract only what's explicitly stated;
never infer, estimate, or invent a date, employer, technology, or number.*

**Constraints:** Accepted formats: `.pdf`, `.docx`, `.txt`, `.md`. Max size **25 MB**. Legacy `.doc`
(binary Word) is rejected outright with a message asking you to save as `.docx` or PDF. A scanned
PDF with no extractable text and no embedded images fails with a clear "no text found" error.

---

## 4. "Enhance with AI" / "Generate from Long"

**What it is:** Per-field AI rewriting on the Description/Responsibilities boxes (and on the
Profile page's bio fields). Long-form boxes get **"Enhance with AI"** (polish existing text);
short-summary boxes get both **"Generate from long"** (draft a summary from the long text) and
"Enhance with AI". The result always lands in a suggestion panel — Replace / Insert below / Copy /
Try again / Discard — never written directly into your text.

**How to use it:** Click the sparkle icon in a rich-text box's toolbar. A suggestion panel appears
with the AI's version; choose what to do with it. If you keep typing in the field while a
suggestion is loading, you'll get a warning before you're allowed to overwrite your own edit.

**Under the hood:** `POST /ai/rewrite`, a single synchronous call (no background job/polling
involved). Prompts explicitly forbid introducing any fact, number, or technology not already
present in your source text. Short-form rewrites use a generate → check length → retry loop (up to
3 attempts) to hit the character limit without an awkward mid-word cut.

**Constraints:** Short-form output caps at 390 characters; long-form at 10,000.

---

## 5. Tasks

**What it is:** Every project has its own task list. A task has a title, optional description,
status (`todo` / `in progress` / `blocked` / `done`), priority (`low` / `medium` / `high` /
`urgent`), an optional due date, and an optional time estimate. Tasks can have **one level** of
subtasks (a subtask can't itself have subtasks).

**How to use it:** From a project's detail page, open its Tasks tab. Add tasks manually, drag to
reorder within a status column, or click **"Break down a document"** to generate a starter list
with AI (see [§6](#6-ai-work-breakdown)).

**Under the hood:** `GET/POST /projects/{id}/tasks`, plus flat `GET/PATCH/DELETE /tasks/{id}`
routes for editing a specific task. Reordering sends the complete ordered list for one status
column at once, not a single "move to position N" instruction.

**Constraints:** Title 1–200 characters, description up to 5,000 characters, time estimate up to
100,000 minutes.

---

## 6. AI Work Breakdown

**What it is:** Turns a document and/or a free-text description of upcoming work into a proposed
task tree for you to review. Every proposed task is labeled either **grounded** (the AI found and
quoted the exact source text that justifies it) or an ungrounded **suggestion** (a reasonable
addition the source doesn't literally state — e.g. "write tests" for a described feature).
Suggestions are shown separately and are never pre-selected for you. Nothing is created until you
explicitly accept.

**How to use it:** From a project's Tasks tab, click **"Break down a document."** Either upload a
document or describe the work in free text (or both), then **"Break it down."** Review the
resulting list — check the boxes for what you want, edit any row's title/description/priority/hours
first if you like — then **"Accept N"**. You can accept in batches; nothing is lost between
batches.

**Under the hood:** `POST /projects/{id}/breakdowns` creates a background job. The AI is
instructed never to invent a name, date, deadline, budget, or specific technology that isn't in
your source material, and never to assign a due date on its own. If the model's output has a
structural mistake (an unknown parent reference, a duplicate id, a title that's too long), the
system repairs it automatically rather than failing the whole job — you'll see a note about what
was fixed.

**Constraints:** Free-text prompt up to 4,000 characters. Up to 60 proposed tasks per job. Accept
up to 60 items, dismiss up to 100, per request.

---

## 7. Project Export (PDF / DOCX)

**What it is:** Download any saved project as a formatted PDF or Word document, preserving your
rich-text formatting (bold/italic/underline, both list types).

**How to use it:** On a project's detail page, use the **PDF** or **DOCX** download buttons.

**Under the hood:** `GET /projects/{id}/export?format=pdf|docx`. DOCX generation goes through
`python-docx`; PDF is rendered by a headless Chromium instance kept running in the background for
fast exports.

---

## 8. Jarvis — the AI Chatbot

**What it is:** A read-only, grounded-first chatbot that floats in the bottom-right corner of every
page. Jarvis can answer questions about your own projects and tasks, analyze patterns across your
whole portfolio, recommend real GitHub repositories, and explain how the platform itself works. It
**cannot create, edit, or delete anything** — it only looks things up and talks about them.

**Its five tools:**
- **project_search** — free-text/technology search over your saved projects.
- **portfolio_analysis** — cross-project aggregates: technology frequency, which projects share a
  given pair of technologies, your project timeline, or how many projects you held each role on.
- **github_search** — a live GitHub search with a real quality bar (minimum stars, not archived,
  pushed to recently), never repeating a repo already suggested to you.
- **task_search** — search your tasks by project, status, or keyword.
- **task_summary** — status/priority counts, how many tasks are overdue, and what's next due.

**The grounding rule:** any claim Jarvis makes about *your own* projects or tasks must come from an
actual tool call in that conversation — never from guessing. General technology questions (e.g.
"what should I use for X") can draw on its own knowledge, but a specific repo recommendation is
always backed by a live `github_search` call rather than a possibly-outdated memory.

**How to use it:** Click the chat bubble on any page. Sessions persist and resume automatically —
reopening the app won't repeat the greeting. A session's title is generated automatically after
your first exchange. Long conversations are quietly summarized in the background so old context
doesn't get lost, without deleting anything from what you see.

---

## 9. Conversations Page

**What it is:** A dedicated page to browse, search, star, and delete your past Jarvis
conversations.

**How to use it:** Go to `/conversations`. Search by title, filter to starred-only, sort by recency.
Clicking a conversation reopens Jarvis's floating widget on that exact conversation, resumed where
you left off. Deleting a conversation asks for confirmation inline before removing it.

---

## 10. AI Provider Settings

**What it is:** Configure your own Gemini and/or OpenAI connection — API key, default model — and
choose which one is your account's default provider.

**How to use it:** Go to Settings → **AI Providers**. Paste an API key, pick a model from the
dropdown, and click **Test connection** to verify it works before saving (this works even before
you hit Save). Mark one provider as your default.

**Under the hood:** Keys are encrypted at rest and never sent back to your browser in plain text —
only a masked version (e.g. `sk-a...3456`) is shown. **Note:** Google is phasing out unrestricted
Gemini API keys starting September 2026; if your key fails the connection test for this reason,
the error message links you to generate a new one.

---

## 11. Agent Persona

**What it is:** A per-account setting — **Business Analyst** (default) or **Technical Developer**
— that changes *how* AI-written text is phrased, never *what facts* it's allowed to state. Business
Analyst phrasing favors business outcomes ("cut response times by 40%"); Technical Developer
phrasing names the actual architecture and tools ("implemented an async caching layer..."). It
applies everywhere AI writes prose for you: extraction, "Enhance with AI", Profile field
enhancement, and the Brag Document Generator.

**How to use it:** Settings → AI Providers → Agent Persona dropdown. Changes apply immediately to
future AI writing — it never rewrites anything you've already generated.

---

## 12. Profile Page

**What it is:** An entirely optional CV-style page. Leaving it blank doesn't degrade anything else
in the app — Jarvis works fully without it, and it's only ever used as soft, self-declared context
(e.g. to bias which GitHub repos get recommended to you), never presented as a verified fact and
never referenced in Jarvis's greeting.

**Sections:** Photo, name, designation/team/organization, skills, speciality, and five AI-enhanced
bio fields: Professional Biography, Work Experience Summary, Career Objective, Key Strengths, and
Responsibilities.

**How to use it:** Go to `/profile`. Each bio field has the same "Enhance with AI" accept/discard
pattern as the project form, plus an optional free-text instruction you can give before generating
a suggestion (e.g. "focus on my leadership experience").

**Constraints:** Professional Biography up to 550 characters; Work Experience Summary, Career
Objective, Key Strengths, and Responsibilities each up to 390 characters; designation/team/
organization/speciality up to 150 characters each. Photo: 5 MB max, JPEG/PNG/WebP only.

---

## 13. Dashboard Suggestions

**What it is:** A "Suggested for you" card on the Dashboard that surfaces real GitHub repositories
related to your most-used technologies — computed in the background, independent of whether you
ever open the chat.

**How to use it:** Just visit `/dashboard`. Dismiss any suggestion you're not interested in; it
won't be shown again. This card only appears when the "Preemptive suggestions" toggle (Settings →
Chatbot) is on.

---

## 14. GitHub Repo Suggestions

**What it is:** The engine behind both Jarvis's live repo recommendations and the Dashboard's
suggestion card. It looks at your most-used technologies across all your saved projects and finds
real, currently-maintained repositories for them — minimum star count, not archived, pushed to
recently.

**How it's triggered:** Automatically whenever you change a project's technologies list, plus a
periodic background refresh every 20 minutes for anyone whose suggestions are stale.

**No-repeat guarantee:** A repo you've already been shown — whether via Jarvis in chat or the
Dashboard card — is never suggested to you again through either surface.

---

## 15. Brag Document Generator

**What it is:** Turns a weekly standup spreadsheet into a formatted, AI-drafted monthly performance
report — a "brag document" — for your own submission (e.g. to an internal ERP/performance-review
system). It combines a deterministic reading of your logged hours with AI narrative grounded in
your own saved [Project Responsibilities](#2-projects) text, so if you only worked on *part* of a
larger project, the report reflects that accurately instead of guessing from a terse spreadsheet
line.

### The spreadsheet format it expects

A single `.xlsx` workbook with **one worksheet per week**, sheet names like
`"Week 32 (Aug 3 - Aug 7)"`. Within each sheet:

- **Column A** — team member name (one row per person; a header/total row is ignored automatically).
- **Column B** — a free-text "weekly pool" notes cell.
- **Five repeating 4-column blocks**, one per weekday (Mon–Fri), each shaped
  **Done | Plan | Blocker | Delivery**. The first cell of each block's "Done" column carries that
  day's date (either a real Excel date or text like `"Aug 3"`).
- The **Done** cell's text is parsed line by line: a plain line like `"Billable:"` or
  `"Non-Billable:"` starts a new category (controlling whether the tasks under it count as billable
  hours); lines starting with `-`, `*`, or `•` are individual task bullets, each expected to end
  with an hour count like `"- Fixed the search bug - 3h"`.
- Leave and holiday days are detected automatically from keywords in the Done/Plan text (e.g.
  `"on leave"`, `"holiday"`, `"eid"`) and are excluded from task parsing.

### How to use it

1. Go to `/brag-documents` and upload your `.xlsx` workbook.
2. The app parses it immediately and shows you the **member name it auto-matched** against your own
   account name, plus every name it actually found in the sheet (in case the auto-match is wrong or
   uncertain — you can pick from a dropdown instead) and the list of months the workbook covers.
   Confirm both, then click **Generate**.
3. A progress stepper tracks the job: reading the spreadsheet → gathering your project context and
   drafting → finalizing the document.
4. Once finished, you'll see:
   - An **hour-stats summary**: total logged hours, expected target hours, holiday/leave
     breakdown, billable vs. non-billable split, and how far over/under target you landed.
   - Three sections of AI-drafted bullets: **Technical Contribution** (grouped by which of your
     saved projects each task belongs to — anything that doesn't clearly match a project lands
     under "On Demand / Miscellaneous" rather than being guessed at), **Team Support &
     Collaboration**, and **Learning & Development**.
   - A **Copy** button on every section (and one "Copy All"), so you can paste straight into
     wherever you need to submit it.
   - **Download DOCX** / **Download PDF** buttons for the finished document.

### How the grounding actually works

The AI is given two things: (1) your real logged work-log lines from the spreadsheet — the only
source of truth for *what was actually done* — and (2) your own saved Project responsibilities/
description text and technologies, for context only. It's explicitly instructed to use your project
data purely to add accurate terminology and clarity to a task you actually logged, never to invent
new work or claim broader ownership of a project than your log supports. No bullet anywhere states
an hour count or a date — every number in the document comes only from the separately-computed hour
stats, never from the AI.

### The hour math (never touched by AI)

Computed with plain arithmetic before the AI is ever called, so a later AI hiccup can never affect
it: a standard 40-hour week (8 hours/day) as the baseline, minus 8 hours per recognized company
holiday. A personal leave day is tracked (shown separately) but does **not** reduce your target —
it shows up as a shortfall instead. A week that spans two calendar months is split at the day level,
so each month only counts its own days.

### Constraints

- Upload format: `.xlsx` only, 25 MB max.
- Member name auto-match uses a fuzzy comparison against your account name; below a confidence
  threshold, you're required to pick manually from the dropdown.
- Generated document caps: up to 30 project groups × 30 bullets each, 30 team-support bullets, 30
  learning bullets. An individual bullet is trimmed (at a word boundary, never mid-word) if it runs
  long.
- Export (DOCX/PDF) is only available once generation has fully succeeded.
