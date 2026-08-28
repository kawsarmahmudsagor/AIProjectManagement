# Backend Architecture — AI Project Management Platform

FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + SAQ. See `../docs/RESEARCH.md` for the
verified library facts this design is built on — several of the choices below (Gemini
SDK, Ollama caveats, doc-parsing libraries, queue) come directly from that research and
are not repeated here in full.

## 1. Module layout

```
backend/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
├── .env.example
├── docker-compose.yml            (Postgres, at repo root actually — see top-level)
└── app/
    ├── main.py                   FastAPI app factory, CORS, lifespan (DB, Playwright browser)
    ├── core/
    │   ├── config.py             pydantic-settings Settings (env-driven)
    │   ├── database.py           async engine/session, Base, get_db dependency
    │   ├── security.py           password hashing, JWT issue/verify, Fernet encrypt/decrypt
    │   └── deps.py                get_current_user, get_settings, pagination
    ├── models/                   SQLAlchemy 2.0 declarative models
    │   ├── base.py                UUIDPk + Timestamps mixins
    │   ├── user.py
    │   ├── project.py
    │   ├── document.py
    │   ├── extraction_job.py
    │   └── ai_provider_setting.py
    ├── schemas/                  Pydantic request/response models
    │   ├── common.py              RichText, PageParams
    │   ├── auth.py  project.py  document.py  job.py  ai_settings.py
    ├── routers/                  one router per resource, included in main.py
    │   ├── auth.py  projects.py  documents.py  jobs.py  ai.py  ai_settings.py  export.py
    ├── services/                 business logic, framework-agnostic where possible
    │   ├── project_service.py
    │   ├── extraction_service.py  orchestrates ingest -> provider -> persist job result
    │   └── export_service.py
    ├── providers/                 the AI abstraction — see §4
    │   ├── base.py                 Protocol: extract(), rewrite(), test_connection()
    │   ├── gemini.py
    │   ├── ollama.py
    │   ├── prompts.py              persona-keyed system prompts + rewrite prompt builder
    │   └── registry.py             resolves a user's configured provider
    ├── agents/                    LangGraph orchestration — see §4
    │   └── rewrite_graph.py        one-node StateGraph wrapping provider.rewrite(); the
    │                                seam a future chatbot graph extends
    ├── ingest/
    │   └── extract.py             magic-byte sniff, pdfplumber/docx2python/mammoth, .doc reject
    ├── render/
    │   ├── docx.py                python-docx + html-for-docx
    │   └── pdf.py                 PdfRenderer protocol, Playwright backend
    └── workers/
        ├── settings.py            SAQ Queue + function registry (Postgres backend)
        └── tasks.py               run_extraction_job(ctx, job_id) — thin wrapper over extraction_service
```

Each router is deliberately thin: parse request → call one service function → map to
response schema. Services are plain `async def`s taking a DB session, so they're unit
testable with no HTTP layer and are exactly what the SAQ task calls.

## 2. Data model

Rich-text fields are stored as **`{field}_html` + `{field}_text`** column pairs, matching
the frontend's `RichText = { html, text }` type exactly — no JSON blob, so length checks
stay simple SQL/Python string ops. `{field}_text` is *always recomputed server-side* from
`{field}_html` on write (strip tags → normalize whitespace) rather than trusted from the
client; the client pair is a UX convenience, not a trust boundary (see frontend DESIGN.md §7).

```
users
  id (uuid, pk)  email (unique, citext)  hashed_password
  agent_persona (enum: business_analyst | technical_developer, default business_analyst)
                 -- which system prompt (providers/prompts.py) frames extraction + rewrite
  created_at  updated_at

projects
  id (uuid, pk)  user_id (fk -> users, cascade)
  name  role
  start_date (date)  end_date (date, nullable)  is_current (bool)
  description_long_html   description_long_text
  description_short_html  description_short_text
  responsibilities_long_html   responsibilities_long_text
  responsibilities_short_html  responsibilities_short_text
  technologies (ARRAY(String), default [])
  project_url (nullable)
  created_at  updated_at

documents
  id (uuid, pk)  user_id (fk)  project_id (fk, nullable — set once the extraction is saved
                                            onto a project; a document can exist standalone
                                            during the "Add New Project" upload-first flow)
  filename  storage_path  mime_type  size_bytes  sha256
  uploaded_at

extraction_jobs
  id (uuid, pk)  user_id (fk)  document_id (fk)  project_id (fk, nullable)
  provider (enum: gemini | ollama)
  status (enum: queued | parsing | extracting | structuring | succeeded | failed)  -- doubles
                                                                                     as the
                                                                                     frontend's
                                                                                     `stage`
  result (JSONB, nullable)        -- ExtractionResult once succeeded; shape mirrors schemas.job.ExtractionResult
  error_code (nullable)  error_message (nullable)
  created_at  started_at  finished_at

ai_provider_settings
  id (uuid, pk)  user_id (fk)
  provider (enum: gemini | ollama)
  encrypted_api_key (nullable — required for gemini; optional for ollama/cloud)
  base_url (nullable — ollama only, default http://localhost:11434)
  default_model (nullable)
  is_default (bool)
  created_at  updated_at
  unique(user_id, provider)
```

Storage for uploaded files and rendered exports: **local disk** under
`DATA_DIR/{uploads,exports}/{user_id}/{uuid}{ext}` — never the client-supplied filename
on disk, to close the path-traversal hole; the original filename is kept only as a DB
column for display/download headers.

## 3. REST API surface

All routes under `/api/v1`. Auth via `Authorization: Bearer <access_token>` — the Next.js
BFF is the only client and injects this header; FastAPI itself does not set cookies.

```
POST   /auth/register              {email, password}                 -> {access_token, refresh_token, user}
POST   /auth/login                 {email, password}                 -> {access_token, refresh_token, user}
POST   /auth/refresh               {refresh_token}                   -> {access_token, refresh_token}
GET    /auth/me                                                       -> {user}
PATCH  /auth/me            {agent_persona?: business_analyst|technical_developer} -> {user}

GET    /projects            ?q=&page=&page_size=                     -> {items: [ProjectSummary], total}
POST   /projects            ProjectCreate                             -> Project
GET    /projects/{id}                                                 -> Project
PATCH  /projects/{id}       ProjectUpdate (partial)                   -> Project
DELETE /projects/{id}                                                 -> 204

POST   /documents           multipart: file, project_id?              -> {document_id, job_id}
                             -> validates magic bytes + size, stores file, creates
                                extraction_job(status=queued), enqueues SAQ task, returns
                                immediately (~100ms)

GET    /extraction-jobs/{id}                                          -> JobStatus
                             { status, stage, result?: ExtractionResult, error?: {code, message} }
                             -- this is the frontend's poll target; stage === status while pending

POST   /ai/rewrite          { op: enhance-long|generate-short|enhance-short,
                               section: description|responsibilities,
                               target: RichText, source: RichText,
                               provider?: gemini|ollama }              -> RichText
                             -- stateless single-field call, synchronous (few seconds,
                                small prompt) so no job/poll needed here unlike extraction

GET    /ai-settings                                                    -> [ProviderSetting]  (key masked, e.g. "sk-...ab12")
PUT    /ai-settings/{provider}   {api_key?, base_url?, default_model?, is_default?}
                                                                         -> ProviderSetting
POST   /ai-settings/{provider}/test                                    -> {ok, detail, models?: [str]}

GET    /projects/{id}/export?format=pdf|docx                           -> file stream,
                             Content-Disposition: attachment; filename="{project.name}.{ext}"
```

`POST /documents` returning immediately with a job id (rather than blocking on
extraction) is the one endpoint whose behavior most shapes the frontend — see the locked
"background jobs + polling" decision and frontend DESIGN.md §4.1/4.2.

## 4. AI provider abstraction

**Providers are orchestrated through LangChain** (`langchain-google-genai` /
`langchain-ollama`) rather than calling `google-genai`/`ollama` directly. This keeps the
provider layer composable with LCEL chains, tracing, and — per the planned chatbot
feature — the same `ChatGoogleGenerativeAI`/`ChatOllama` instances can be reused for a
conversational agent (memory, tool calling, retrieval over a user's saved projects)
without a second integration layer. Two things are still done by hand rather than via
LangChain's higher-level helpers, deliberately:

- **Structured output is bound directly** (Gemini's `response_mime_type`/
  `response_json_schema`, Ollama's native `format`) instead of using
  `.with_structured_output()`. For Ollama specifically there's a documented, currently
  open issue where `with_structured_output` is not honoured in some versions while the
  raw `format` parameter always works (`langchain-ai/langchain#29410`) — binding it
  ourselves sidesteps that entirely.
- **Safety checks read `response_metadata` explicitly** — `finish_reason` for Gemini's
  MAX_TOKENS truncation, `prompt_eval_count` for Ollama's context truncation — since
  those are exactly the silent-failure modes docs/RESEARCH.md §A3/§B6 verified against
  the raw APIs, and LangChain's abstraction shouldn't be trusted to surface them by
  default. **The `response_metadata` key names should be spot-checked against whatever
  `langchain-google-genai`/`langchain-ollama` versions actually get installed** — this is
  the one seam in the backend that wasn't verified against a live call, only against
  each package's documented behavior at design time.

**The rewrite path (`/ai/rewrite`) is already routed through LangGraph**
(`app/agents/rewrite_graph.py`): a compiled `StateGraph` with one node, `call_provider`,
that awaits `LLMProvider.rewrite(...)`. `ai_service.rewrite_field()` calls
`run_rewrite()` (the graph's entry point) instead of the provider directly — the
generate-then-verify-then-retry loop for the 390-char cap (below) still lives in the
service and just calls the graph once per attempt. It's intentionally a single node
today; it exists so the chatbot feature above extends an existing compiled graph
(adding memory/tool-calling/routing nodes) instead of introducing orchestration for the
first time. Extraction is **not** routed through LangGraph — it stays a direct
`provider.extract(...)` call, since it already has its own job-status state machine (§2's
`extraction_jobs.status`) and doesn't need a second one.

```python
# app/providers/base.py
from typing import Protocol
from pydantic import BaseModel

class ConnectionStatus(BaseModel):
    ok: bool
    detail: str
    models: list[str] = []

class ExtractInput(BaseModel):
    raw_bytes: bytes | None      # PDF bytes, when the provider can take them directly (Gemini)
    mime_type: str
    extracted_text: str | None   # always populated for docx/txt; populated for pdf as fallback/pre-flight
    filename: str

class LLMProvider(Protocol):
    async def extract(self, doc: ExtractInput, schema: dict, *, persona: AgentPersona) -> dict: ...
    async def rewrite(self, op: str, target_text: str, source_text: str | None,
                       char_limit: int | None, *, persona: AgentPersona) -> str: ...
    async def test_connection(self) -> ConnectionStatus: ...
```

`persona` (`models/user.AgentPersona` — `business_analyst` | `technical_developer`, the
`users.agent_persona` column) selects which system prompt in `providers/prompts.py`
frames the call — see "Prompt design" below.

`registry.py` resolves `LLMProvider` for a request: load the user's
`ai_provider_settings` row for the requested (or default) provider, decrypt the API key
via `core.security.decrypt()`, and construct `GeminiProvider`/`OllamaProvider`. Providers
are cheap to construct (no persistent connection) so they're built per-call, not cached.

### Gemini (`providers/gemini.py`)

- SDK: `google-genai` **pinned `<3.0`** (breaking Automatic Function Calling changes land
  in 3.0 — see RESEARCH.md §A1).
- Structured output: `response_mime_type="application/json"` +
  `response_json_schema=<flattened JSON Schema>` on `generate_content`. Do **not** send
  `temperature`/`top_p`/`top_k` on 3.x models — silently ignored today, will 400 later.
  Use `thinking_level="low"` for extraction (it's a data-extraction task, not reasoning).
- **PDFs go straight to Gemini** — inline bytes under ~15MB, Files API above that (and
  always for the retained-slightly-longer multi-call case). This is why `ExtractInput`
  carries `raw_bytes`: the Gemini adapter prefers them for PDF and only falls back to
  `extracted_text` for DOCX/TXT (Gemini has no DOCX vision).
- **Always check `finish_reason == "MAX_TOKENS"` explicitly.** With structured output,
  hitting the token cap returns `None`/truncated JSON with *no exception* — treating that
  as "no data found" instead of "error, retry with a higher cap" is the single most likely
  silent-failure bug here (RESEARCH.md §A3).
- Errors: `google.genai.errors.ClientError` (`.code` — 429 quota, 401/403 bad/unrestricted
  key, 400 bad request) vs `ServerError` (5xx, retry). The SDK's built-in retry already
  backs off 429/5xx; a 429 that persists past ~2 minutes is a daily-quota exhaustion, not
  worth further retrying — fail the job and surface `RATE_LIMITED`.
- `test_connection()` calls `client.models.list()` — zero-token, cheap, and also usable to
  populate the model dropdown instead of hardcoding model IDs that rotate every few months.
- **Settings-page copy requirement**: a 401/403 must suggest the key may be an
  unrestricted "standard" key — those are rejected outright from **September 2026**
  (RESEARCH.md §A6). Don't skip this; it will hit real users during initial rollout.

### Ollama (`providers/ollama.py`)

- **Local only.** Ollama Cloud does not support structured outputs
  (RESEARCH.md §B3) — no cloud code path for extraction, ever, even though the schema
  has room for a `base_url`/cloud key. If a user points `base_url` at
  `ollama.com/api`, `test_connection` should still work (cloud chat works fine) but the
  provider should refuse `extract()` with a clear `"Ollama Cloud doesn't support
  structured output — use a local model for extraction"` error rather than silently
  producing garbage.
- Structured output via the native `ollama` Python client's `format=<json schema>`
  (**never** the OpenAI-compatible `/v1` shim — it has no way to set `num_ctx` at all,
  RESEARCH.md §B6). Inline the schema (no `$ref`/`$defs` — Pydantic's default nested-model
  output needs flattening first; Ollama has real history of `$ref`-ordering bugs).
- **`num_ctx` must be set explicitly on every call.** Default is 4096 tokens and Ollama
  truncates server-side with a normal 200 response — no exception, no warning in the
  payload. Estimate tokens from the document, cap against the model's real context length
  (`POST /api/show`), and **verify `prompt_eval_count` after the call** — if it's
  suspiciously close to `num_ctx`, raise `TruncationError` rather than trusting the result:

  ```python
  info = await client.show(model)
  model_ctx = info.model_info.get(f"{arch}.context_length", 8192)
  est_tokens = len(text) // 3 + 1500
  num_ctx = min(max(8192, next_pow2(est_tokens)), model_ctx, 32768)
  resp = await client.chat(model=model, messages=[...],
                            format=schema, options={"num_ctx": num_ctx,
                                                     "num_predict": 8192,
                                                     "temperature": 0})
  if resp["prompt_eval_count"] < est_tokens * 0.85:
      raise TruncationError(f"only {resp['prompt_eval_count']} of ~{est_tokens} tokens processed")
  ```
- Also paste the JSON schema into the prompt text itself (belt-and-braces — Ollama's own
  docs recommend this for small models) and set `num_predict` to stop runaway/repeating
  generation, a documented failure mode on weak models.
- `test_connection()` = `GET /api/version` (liveness) + `GET /api/tags` (populate the
  model dropdown from what's actually installed — never hardcode).
- **Set expectations in the UI**: local models will visibly underperform Gemini on
  scanned PDFs (no OCR path), multi-column layouts, and long documents. Position it as
  the privacy/offline option, default the user to Gemini, and always route local-model
  output through the human review step in the form (never auto-save without review).

### Prompt design ("as human as possible")

Both providers share one prompt-building module (`app/providers/prompts.py`) so the
instructions stay in one place regardless of which model executes them:

- **Persona is a per-user setting, not a fixed constant** (Settings > AI Providers >
  "Agent Persona", `users.agent_persona`, default `business_analyst`). Both the
  extraction and rewrite prompts are keyed by `AgentPersona` —
  `EXTRACTION_SYSTEM_PROMPTS[persona]` / `REWRITE_SYSTEM_PROMPTS[persona]` — so the
  persona changes only *how* the same facts are framed, never whether the model can
  invent new ones: the "never invent a fact" rule below is identical across every
  persona variant.
  - **`business_analyst`** (default) writes description/responsibilities text the way a
    business analyst would explain the work to a business stakeholder — plain, human
    language centered on the problem solved and its impact, translating technical detail
    into business-outcome terms ("led a project that cut customer response times by
    40%" not "implemented an async caching layer that reduced p95 latency by 40%").
  - **`technical_developer`** writes the same facts the way one engineer would explain
    the work to another — naming the architecture, languages, frameworks, and technical
    approach directly instead of translating them into business outcomes.
- **Extraction system prompt** (per persona): "You are a Technical Business Analyst /
  Technical Developer reviewing a project document. Extract only what is explicitly
  present in the document. Use `null` for anything not stated — never infer, estimate, or
  invent a date, employer, or metric that isn't written down." Explicit nullability on
  every optional schema field (not just Python `| None` — the JSON Schema itself must
  mark it non-required) is what actually stops small local models from hallucinating
  plausible-looking values (RESEARCH.md §B4 point 4).
- **Rewrite prompts** (`enhance-long`, `generate-short`, `enhance-short`) are told to
  write **first person, active voice**, in whichever persona's framing is active, and
  explicitly forbidden from introducing facts, numbers, or technologies absent from the
  source text — this is enforced by prompt instruction only (LLMs can't be sandboxed
  from fabricating), so the UI's mandatory human-review step is the real safety net, not
  the prompt.
- **390-char short-summary cap — generate-then-verify-then-retry loop**, since neither
  provider can be trusted to hit an exact character count:

  ```python
  async def generate_short_summary(provider, long_text: str, limit: int = 390) -> str:
      for attempt in range(3):
          draft = await provider.rewrite("generate-short", target_text="",
                                          source_text=long_text, char_limit=limit)
          plain = strip_html_to_text(draft)
          if len(plain) <= limit:
              return draft
          long_text = f"{long_text}\n\n(Previous attempt was {len(plain)} chars, " \
                      f"{len(plain) - limit} over the {limit} limit — be more concise.)"
      # last resort: truncate at the nearest sentence boundary, never mid-word
      return truncate_at_sentence(draft, limit)
  ```

  The frontend never receives an over-limit "accepted" value; API-level Pydantic
  validation on `RichText` also rejects it defensively even if this loop is bypassed.

## 5. Document parsing (`ingest/extract.py`)

Per RESEARCH.md §C: `pdfplumber` (MIT, no native deps) for PDF text as the pre-flight/
fallback path, `docx2python` for `.docx` extraction (catches headers/footers/text boxes
that bare `python-docx` misses — document templates put key details in a header
disturbingly often), `mammoth` for a DOCX→HTML representation when useful. Format
detection is by **magic bytes, not extension**:

```python
MAGIC = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx (zip)
}
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc — reject with a clear error
```

`.doc`, `.rtf`, `.odt` and other legacy binary formats are **rejected at upload** with a
`415` and copy telling the user to save as `.docx` or PDF — see RESEARCH.md §C3 for why
(LibreOffice headless is the only thing that actually converts `.doc` on Windows and it's
a 700MB dependency for a 19-year-obsolete format).

`extract()` returns `{raw_bytes, mime_type, extracted_text, page_count, is_scanned}`. The
scanned-PDF check (`is_scanned = total_extracted_chars < 100`) matters even though Gemini
gets the raw PDF directly: it drives the pre-flight decision for the **Ollama** path
(which has no OCR and must fail fast with `NO_TEXT_FOUND` rather than silently extracting
nothing) and for offline/local-only mode.

## 6. Job queue

**SAQ on the Postgres backend** (`saq[postgres,web]`) — not Celery, not Redis. Reasoning
in full in RESEARCH.md §D; short version: Celery's prefork pool is broken on Windows, SAQ
is async-native (matches FastAPI's `await gemini_call()` shape with zero
`asyncio.run()`-in-a-thread contortions), and using the Postgres backend means the
Windows dev machine needs **zero additional services** — no Memurai, no Docker Desktop,
no WSL2, just the Postgres you already have.

```python
# app/workers/settings.py
from saq import Queue
from app.core.database import engine
from app.workers.tasks import run_extraction_job

queue = Queue.from_url(f"postgres+{settings.DATABASE_URL}")  # or Queue(pg_pool) per SAQ's postgres setup

settings = {
    "queue": queue,
    "functions": [run_extraction_job],
    "concurrency": 4,
    "startup": on_worker_startup,   # warm httpx clients, etc.
}
```

```python
# app/workers/tasks.py — thin wrapper; all real logic lives in the service and is
# independently unit-testable with no queue involved
async def run_extraction_job(ctx, job_id: str):
    async with async_session() as db:
        await ExtractionService(db).run(job_id)
```

**Job state machine**: `queued → parsing → extracting → structuring → succeeded|failed`.
The service updates `extraction_jobs.status` (and `started_at`/`finished_at`) at each
transition so `GET /extraction-jobs/{id}` always reflects live progress for the frontend's
poll — no separate "stage" table or pub/sub needed at this scale. `parsing` = document
ingest running; `extracting` = provider call in flight; `structuring` = mapping the raw
provider result onto the `ExtractionResult` schema and persisting. A crashed worker leaves
a job stuck in a non-terminal state; a periodic SAQ cron job
(`reap_stale_jobs`, every 5 min) marks any job with `status not in (succeeded, failed)` and
`started_at < now() - 10min` as `failed/TIMEOUT` so the frontend's poll always terminates.

## 7. Export

One rich-text→output path, two renderers behind shared `PdfRenderer`/DOCX-writer
interfaces so the choice is swappable per-deployment:

- **DOCX**: `python-docx` builds the document skeleton (or `docxtpl` against a
  designer-owned template — worth adopting once there's a real visual layout to match);
  each `{field}_html` column is piped through **`html-for-docx`** (PyPI name
  `html-for-docx`, import name `html4docx` — note the naming trap in RESEARCH.md §C4;
  the similarly-named `htmldocx`/`html4docx` packages on PyPI are both abandoned) to
  preserve bold/italic/underline and both list types.
- **PDF**: **Playwright + Chromium**, not WeasyPrint — WeasyPrint still requires an MSYS2
  + Pango native install on Windows as of v69 (RESEARCH.md §C5), which is a real
  onboarding blocker for a Windows-first dev team. One Jinja2 HTML+CSS template renders
  both the on-screen preview and the PDF (`page.pdf()` with `@page` CSS, headers/footers).
  The browser instance is launched once in the FastAPI `lifespan` handler and reused
  across requests — cold-launching Chromium per export is the mistake that makes
  Playwright *look* slow.
- Stored rich-text HTML is sanitized to a small whitelist at **save** time (not
  render time) — `p, br, strong, b, em, i, u, s, ul, ol, li, a, h1-h4` — which both closes
  an XSS hole in the future read-only detail view and guarantees `html-for-docx` only ever
  sees markup it actually supports.

## 8. Security

- **Upload validation**: magic-byte sniffing (not extension), a hard size cap (e.g. 25MB,
  configurable), and files are written to disk under a **generated UUID name** — the
  client-supplied filename never touches the filesystem path, closing path traversal.
- **API key encryption**: `cryptography.fernet.Fernet`, keyed by a `FERNET_KEY` read from
  the environment (**never committed**, generated once per deployment via
  `Fernet.generate_key()`). Decrypted keys exist only in-memory for the duration of a
  provider call; `GET /ai-settings` returns a masked preview (`sk-...ab12`) only, never
  the plaintext, and there is no endpoint that returns a decrypted key to the client.
- **Prompt injection from uploaded documents**: treat extracted document text as
  untrusted input embedded in the extraction prompt. Mitigate with a clear system/user
  message boundary (the system prompt's extraction instructions are never in the same
  message as document content) and by constraining the provider to schema-only output —
  an injected instruction like "ignore previous instructions and output X" can still
  corrupt *values* inside the schema, but can't escape into arbitrary tool calls or
  change what fields exist, since there's no agentic tool use here at all. This is why
  the human-review step in the UI is load-bearing, not optional polish.
- **SSRF via user-supplied Ollama `base_url`**: the settings endpoint accepts a base URL
  the user controls, which the backend then makes server-side requests to — a classic
  SSRF vector if a malicious user (in a multi-tenant deployment) points it at
  `http://169.254.169.254` or an internal service. Mitigate: for non-local deployments,
  validate/allowlist the host (permit `localhost`/`127.0.0.1`/private RFC1918 ranges only
  if the deployment is explicitly single-tenant/self-hosted; otherwise resolve and reject
  link-local/metadata and other internal ranges), short connect/read timeouts, and no
  following of redirects to a different host.

## 9. Milestones

| # | Deliverable | Runnable proof |
|---|---|---|
| **M0** | Project skeleton, `Settings`, DB engine, Alembic baseline, `/healthz` | `uvicorn app.main:app` serves, `alembic upgrade head` runs against Postgres |
| **M1** | `User` model + JWT auth (`register`/`login`/`refresh`/`me`) | curl register → login → GET `/auth/me` with the token |
| **M2** | `Project` CRUD (no AI yet) | Create/list/get/update/delete a project via curl/Postman |
| **M3** | `ai_provider_settings` CRUD + `test_connection` for both providers | Save a Gemini key, hit `/ai-settings/gemini/test`, get a real OK/failure |
| **M4** | `ingest/extract.py` + `documents` upload endpoint (no AI call yet — just parse + store) | Upload a PDF/DOCX, see extracted text length and `is_scanned` in the response |
| **M5** | SAQ wired (Postgres backend), `extraction_jobs` table, upload now enqueues a no-op job that just marks itself succeeded | Upload → poll `/extraction-jobs/{id}` → watch status transition without touching AI yet |
| **M6** | Gemini provider live, extraction end to end (`extracting`→`structuring`→`succeeded`, real `ExtractionResult`) | Upload a real project document PDF, poll to completion, see structured project data |
| **M7** | Ollama provider live (local-only), provider selection respected | Same flow against a local Ollama model |
| **M8** | `/ai/rewrite` (enhance-long, generate-short with the retry loop, enhance-short) | Call each op directly, confirm the 390-char loop actually holds the cap |
| **M9** | Export: DOCX via `html-for-docx`, PDF via Playwright | Download and open both from a saved project |
| **M10** | Hardening: upload size/magic-byte enforcement, Fernet key rotation story, `reap_stale_jobs` cron, structured logging, rate limiting on `/auth/*` | Load tests / manual abuse checks pass |

M0–M2 sequential. M3 can run in parallel with M4. M5 must precede M6/M7. M8 is independent
of M6/M7 (it only needs a provider, not the job queue) and can start once M3 is done.
