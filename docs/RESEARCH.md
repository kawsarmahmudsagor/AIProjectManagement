I have enough verified material. No Write tool is available in this read-only research role, so here is the full reference document.

---

# Integration Reference: Gemini + Ollama + Doc Parsing + Job Queues
**Verified August 21, 2026.** Every non-obvious claim is cited. Items I could not confirm from a primary source are marked **UNVERIFIED**.

---

## ⚠️ Read these five corrections first

| # | Your premise | Reality |
|---|---|---|
| 1 | "`response_mime_type`/`response_schema`" | Partly stale. For `generateContent` the current pairing is **`response_mime_type` + `response_json_schema`**. And there is now a **whole new primary API surface** (Interactions API, GA 22 June 2026) where the parameter is **`response_format`**. `generateContent` is officially labeled **"legacy"** in Google's own docs nav. |
| 2 | Implied you'd set `temperature=0` for deterministic extraction | **All Gemini 3.x models ignore `temperature`, `top_p`, `top_k`.** Google's migration checklist says to *strip* them. They're currently accepted-and-ignored silently; future models will 400. `candidate_count` is unsupported. |
| 3 | "Ollama Cloud … which models are offered" | Ollama Cloud **does exist** and works as you described (Bearer auth, `https://ollama.com/api`). **BUT: "Ollama's Cloud currently does not support structured outputs."** That is a direct quote from Ollama's own docs. This kills Ollama Cloud for your extraction path. |
| 4 | Not mentioned | **Gemini API key auth is changing right now.** Unrestricted "standard" keys were blocked 19 June 2026; **all** standard keys get rejected in **September 2026** — you must be on "auth keys". Your settings page needs to handle this. |
| 5 | Not mentioned | **The Gemini free tier trains on your data and human reviewers may read it.** You are processing project documents that can contain personal information (names, addresses, employment history). Free tier is legally/ethically wrong for this. |

---

# A. Google Gemini API (API key, not Vertex)

## A1. Current SDK — `google-genai`

**Current:** `pip install google-genai` → package `google-genai`, **v2.19.0, released 2026-08-19** (verified live from PyPI JSON API).

**Dead:** `google-generativeai` — **deprecated/EOL 30 November 2025**. Its GitHub repo is literally renamed [`google-gemini/deprecated-generative-ai-python`](https://github.com/google-gemini/deprecated-generative-ai-python). Last PyPI release 0.8.6 (2025-12-16). It cannot access Gemini 3.x features (`thinking_level`, 100 MB uploads, custom tools). Do not use it. ([Gemini API libraries](https://ai.google.dev/gemini-api/docs/libraries))

**Also dead:** `vertexai.generative_models` — permanent removal **24 June 2026**. Irrelevant to you (you're on API key) but worth knowing when reading old blog posts. ([TheRouter](https://therouter.ai/news/vertex-ai-sdk-migration-gemini-enterprise-agent-platform/))

> **Pin `google-genai<3.0.0`.** The README warns of breaking Automatic Function Calling changes in 3.0. ([README](https://github.com/googleapis/python-genai))

### Client init + generate (legacy `generateContent` path — recommended for you)

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="...")   # or env GEMINI_API_KEY / GOOGLE_API_KEY

resp = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="...",
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=MySchema.model_json_schema(),
    ),
)
```
Env var note: SDKs auto-read `GEMINI_API_KEY`, and `GOOGLE_API_KEY` if set; **if both are present `GOOGLE_API_KEY` wins** — a classic "why is it using the wrong key" bug.

### The new Interactions API (know it exists; you probably don't need it yet)

- Public beta Dec 2025 → **GA 22 June 2026**. `POST /v1beta/interactions`, Python `client.interactions.create(...)`. ([blog.google](https://blog.google/innovation-and-ai/technology/developers-tools/interactions-api-general-availability/), [docs](https://ai.google.dev/gemini-api/docs/interactions-overview))
- Different shape: `input` (typed content blocks) instead of `contents`; `previous_interaction_id` for server-side state; `interaction.output_text` convenience accessor; typed execution steps; Flex/Priority tiers; 55-day retention on paid.
- Structured output moves to a flattened top-level `response_format`:

```python
interaction = client.interactions.create(
    model="gemini-3.7-flash",
    input=[{"type": "text", "text": "..."}],
    response_format=[{
        "type": "text",
        "mime_type": "application/json",
        "schema": Recipe.model_json_schema(),
    }],
)
data = interaction.output_text
```
([Migration guide](https://ai.google.dev/gemini-api/docs/migrate-to-interactions))

- Google's commitment: *"the legacy generateContent API remains fully supported ... while we expect frontier capabilities for long-running models and agents to increasingly land exclusively on the Interactions API."* **No sunset date announced.**

**Recommendation:** build on `generateContent`. Your workload is one-shot stateless extraction — you gain nothing from server-side state or managed agents, and `generateContent` has far more community examples. Isolate the call in one provider module so the swap is a 20-line change later.

## A2. Current model IDs, pricing, context

Model list verified from [ai.google.dev/gemini-api/docs/models](https://ai.google.dev/gemini-api/docs/models); pricing from [ai.google.dev/gemini-api/docs/pricing].

| Model ID | Status | Context | Paid $/1M in → out | Free tier |
|---|---|---|---|---|
| `gemini-3.7-flash` | **stable, latest Flash** | 1,048,576 in / 65,536 out | **$0.75 → $3.75** (intro, thru 2026-12-31; then $1.50 → $7.50) | yes |
| `gemini-3.6-flash` | stable | 1M | $0.75 → $3.75 (same intro schedule) | yes |
| `gemini-3.5-flash` | stable | 1M | $1.50 → $9.00 | yes |
| `gemini-3.5-flash-lite` | stable | 1M in / 64k out, cutoff Mar 2026 | **$0.30 → $2.50** (batch/flex $0.15 → $1.25) | yes |
| `gemini-3.1-flash-lite` | stable | 1M | **$0.25 → $1.50** (batch $0.125 → $0.75) | yes |
| `gemini-3.1-pro-preview` | preview | — | $2.00 → $12.00 (≤200k prompt; higher above) | no |
| `gemini-2.5-flash` | stable (older gen) | 1M | $0.30 → $2.50 | yes |
| `gemini-2.5-flash-lite` | stable | 1M | — | yes |
| `gemini-2.5-pro` | stable | 1M | $1.25 → $10.00 | yes |

**Shut down** (will hard-fail): `gemini-2.0-flash`, `gemini-2.0-flash-lite`, `gemini-3-pro-preview`, `gemini-3.1-flash-lite-preview`. Note `gemini-3-pro-preview` shut down **9 March 2026** — if any tutorial you follow uses it, it's dead. Batch API ≈ 50% of standard rates across the board.

Context-window figures corroborated by [OpenRouter's 3.7 Flash card](https://openrouter.ai/google/gemini-3.7-flash) and the [DeepMind 3.5 Flash-Lite model card](https://deepmind.google/models/model-cards/gemini-3-5-flash-lite/).

### My picks for your two jobs

- **Cheap single-field rewrite → `gemini-3.1-flash-lite`** ($0.25/$1.50). Cheapest current-gen. `gemini-3.5-flash-lite` if you want the newer one and ~350 tok/s.
- **Long-document structured extraction → `gemini-3.5-flash`** as default. If cost-sensitive, `gemini-3.7-flash` is actually *cheaper on input* ($0.75 vs $1.50) and newer — but it's tuned for coding/agentic work and defaults to `thinking_level: "medium"`, so you pay for reasoning tokens you may not need. Benchmark both on 10 real project documents; use `thinking_level="low"` for extraction.
- **Avoid Pro.** Extraction from a clean text/PDF is not a reasoning-hard task, and Pro is 8× the input cost of 3.7 Flash. Third-party sources say Pro models became paid-only 1 April 2026 ([pecollective](https://pecollective.com/tools/gemini-free-tier-guide/)) — **UNVERIFIED** against official docs.

### Gemini 3.x generation-config gotchas (this will bite you)

- **`temperature`, `top_p`, `top_k`: remove them.** Google's own checklist says *"Strip `temperature`, `top_p`, and `top_k` from generation configs"*. They are silently ignored today; future models return HTTP 400. ([What's new in Gemini 3.7 Flash](https://ai.google.dev/gemini-api/docs/latest-model))
- **`thinking_budget` → `thinking_level`**, a string enum `"low" | "medium" | "high"`, default `"medium"`. `thinking_budget` still works for back-compat; never send both.
- **`candidate_count` is unsupported.**
- **Remove prefilled model turns** — Gemini 3.x enforces turn-validation rules. If you were "priming" the model with a fake assistant turn starting with `{`, that breaks.

## A3. Structured output

**Current field names (generateContent):**
- `response_mime_type = "application/json"` — required.
- `response_json_schema` — takes a plain JSON Schema dict. **This is the one to use.**
- `response_schema` — legacy; takes the SDK `types.Schema` object *or* a Pydantic class directly. If set, `response_json_schema` must be omitted (mutually exclusive).
- Docs guidance: *"If `response_schema` doesn't process your schema correctly, try using `response_json_schema` instead."* ([DeepWiki: python-genai structured outputs](https://deepwiki.com/googleapis/python-genai/3.5-structured-outputs-and-response-schemas))

**Pydantic: yes, both ways.** Pass the class to `response_schema` (then `response.parsed` gives you a hydrated model instance — **`.parsed` only populates on the `response_schema` path**), or pass `Model.model_json_schema()` to `response_json_schema` and validate yourself.

**What got better (5 Nov 2025):** Google added real JSON Schema support to *all* actively supported models, specifically enabling `anyOf`, `$ref`, `minimum`, `maximum`, `additionalProperties`, `type: "null"`, `prefixItems`. Also **implicit property ordering** — output key order now matches your schema key order on 2.5+ (this used to require the `propertyOrdering` hack). ([Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/))

**Supported schema surface** ([structured output docs](https://ai.google.dev/gemini-api/docs/structured-output)):
- types: `string`, `number`, `integer`, `boolean`, `object`, `array`, `null`
- object: `properties`, `required`, `additionalProperties`
- string: `enum`, `format` (`date-time`, `date`, `time`)
- number/integer: `enum`, `minimum`, `maximum`
- array: `items`, `prefixItems`, `minItems`, `maxItems`
- annotations: `title`, `description`

**NOT supported / risky:** the docs say only *"Not all JSON Schema features are supported"* and *"Very large or deeply nested schemas may be rejected"* without enumerating. Assume unsupported: `pattern` (regex), `oneOf`/`allOf` (only `anyOf` is confirmed), `const`, `dependentSchemas`, `if/then/else`, `uniqueItems`, `propertyNames`, string `minLength`/`maxLength`. **UNVERIFIED individually** — test yours.

### Working sample

```python
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class Bullet(BaseModel):
    text: str

class Project(BaseModel):
    project_name: str
    client: str | None = None
    role: str | None = None
    start_date: str | None = Field(None, description="ISO YYYY-MM or YYYY-MM-DD")
    end_date: str | None = None
    technologies: list[str] = []
    responsibilities: list[str] = []

class Extraction(BaseModel):
    projects: list[Project]
    confidence_notes: list[str] = []

client = genai.Client(api_key=KEY)

resp = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=[document_part, "Extract every project into the schema. "
                             "Use null for fields not present. Do not invent data."],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=Extraction.model_json_schema(),
        thinking_level="low",          # 3.x; NOT thinking_budget
        max_output_tokens=32768,       # see failure mode below
        system_instruction="You are a strict data extractor. Never fabricate.",
        # NO temperature / top_p / top_k on 3.x
    ),
)
data = Extraction.model_validate_json(resp.text)
```

### Known failure modes — handle all of these

1. **Empty response / `None` on MAX_TOKENS.** With structured output, if generation hits `max_output_tokens`, both `response.text` and `response.parsed` come back `None` or truncated mid-JSON. ([python-genai #1039](https://github.com/googleapis/python-genai/issues/1039), [batch API report](https://discuss.ai.google.dev/t/gemini-batch-api-invalid-json-when-finish-reason-is-max-tokens/143697))
2. **Thinking tokens eat `max_output_tokens`.** `thoughts_token_count + output_token_count` is measured against `max_output_tokens`. Thinking is on by default on 2.5/3.x Flash, so a "reasonable" 4096 limit produces empty output. ([python-genai #782](https://github.com/googleapis/python-genai/issues/782))
   → **Always check `candidate.finish_reason == "MAX_TOKENS"` explicitly and surface it as a real error.** Never treat `None` as "no data found."
3. **Deep/large schemas rejected.** Flatten. Avoid >3 levels of nesting; split a 60-field form into 2–3 calls.
4. **`$ref` ordering bugs** existed in Ollama and historically in Gemini; safest is Pydantic with `model_json_schema(ref_template=...)` inlined, or just avoid reusing sub-models where you can.
5. **Syntactically valid ≠ semantically correct.** Docs explicitly warn output "requires application-level semantic validation." Always `model_validate_json` and treat `ValidationError` as a retry-once-then-fail.

## A4. PDFs directly to Gemini — **yes, and you should**

From [document-processing docs](https://ai.google.dev/gemini-api/docs/document-processing):
- **Limits: PDF up to 50 MB or 1000 pages.**
- **Two paths:** inline base64 bytes (small docs), or **Files API** (larger / multi-turn). Files API decouples upload from request, lowers latency and bandwidth. Files are **free** and retained **48 hours**.
- Files API general limits: **2 GB per file, 20 GB per project**, free in all regions. Use Files API once a request exceeds the **100 MB** total-request threshold. ([Files docs](https://ai.google.dev/gemini-api/docs/files))
- **Tokenization: ~258 tokens per page.** Pages are rasterized and scaled to between 768×768 and 3072×3072.
- **Big Gemini 3 change:** *natively embedded text in PDFs isn't charged* — only page-image processing consumes tokens, billed under the `IMAGE` modality. So a 30-page text document ≈ 30 × 258 ≈ 7,700 tokens ≈ **$0.006 on 3.7 Flash**. Negligible.
- **Only PDF gets real document vision.** TXT/MD/HTML/XML are accepted but "convert to plain text, losing formatting and visual elements."

```python
f = client.files.upload(file="document.pdf")
resp = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=[f, "Extract projects per schema."],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=Extraction.model_json_schema(),
    ),
)
client.files.delete(name=f.name)   # be a good citizen
```

### Direct-PDF vs local text extraction — my recommendation

**Send the PDF directly to Gemini. Keep local extraction as fallback, not as the primary path.**

Why direct wins for project documents specifically:
- Many are **layout-heavy**: two-column templates, sidebars, tables, icon-labelled blocks. Every text extractor destroys reading order on these. Gemini sees the rendered page.
- **Scanned/image-only PDFs** work with zero extra OCR dependency. This is the single biggest reliability win.
- It eliminates PyMuPDF's AGPL problem and WeasyPrint-class native-dependency pain from your ingest path.
- Cost is trivial (see above).

Why keep local extraction:
- **Ollama has no PDF vision path you can rely on** — the local models you'd realistically run are text-first. So your Ollama branch *needs* local text extraction anyway. Build it regardless.
- Fallback when a PDF exceeds 50 MB / 1000 pages, or when the user is offline.
- Cheap pre-flight: extract text locally to detect "0 characters → this is a scan" and to compute a token estimate before you spend money.

**Design:** `ingest()` returns `{raw_bytes, mime, extracted_text, page_count, is_scanned}`. Gemini adapter prefers `raw_bytes` for PDF, `extracted_text` for DOCX/TXT (Gemini has no DOCX vision — you must convert). Ollama adapter always uses `extracted_text`.

## A5. Rate limits and error handling

**Google no longer publishes static per-tier tables.** The [rate-limits page](https://ai.google.dev/gemini-api/docs/rate-limits) now says limits "can be viewed in Google AI Studio" and points at `https://aistudio.google.com/rate-limit`. Do not hardcode limits; read the dashboard.

Tiers (official): **Free** (project/trial) → **Tier 1** (billing enabled) → **Tier 2** ($100+ spent, 3+ days since first payment) → **Tier 3** ($1,000+ spent, 30+ days). Free→Tier 1 is instant; later upgrades ≤10 min.

Third-party numbers, **UNVERIFIED**: Gemini 3 Flash free = 10 RPM / 250k TPM / 1,500 RPD; 3.1 Flash-Lite = 15 RPM ([pecollective](https://pecollective.com/tools/gemini-free-tier-guide/)).

### Exception types (verified from `google/genai/errors.py`)

```
APIError                          # base, non-standard status codes
├── ClientError                   # HTTP 4xx  → 429 quota, 400 bad schema, 401/403 bad key
└── ServerError                   # HTTP 5xx  → retry
UnknownFunctionCallArgumentError  # ValueError subclass
UnsupportedFunctionError          # ValueError subclass
FunctionInvocationError           # ValueError subclass
UnknownApiResponseError           # ValueError subclass — response not parseable as JSON
```

There is **no dedicated `RateLimitError`**. You must inspect the code:

```python
from google.genai import errors

try:
    resp = client.models.generate_content(...)
except errors.ClientError as e:
    if e.code == 429:            # RESOURCE_EXHAUSTED
        ...                      # backoff / surface "quota exhausted" to the user
    elif e.code in (401, 403):
        ...                      # invalid or unrestricted key → settings page
    elif e.code == 400:
        ...                      # bad schema / bad request — do NOT retry
    else:
        raise
except errors.ServerError:
    ...                          # retryable
```

**Retry is already built in.** The SDK retries transient errors (429 + 5xx) up to ~4 attempts, initial delay ~1s, max 60s, with exponential backoff. Configure via `HttpRetryOptions` on the client (`initial_delay`, `attempts`, `http_status_codes`). **Caveat:** the SDK uses fixed exponential backoff and **ignores the server-supplied `google.rpc.RetryInfo.retryDelay`** ([issue #1875](https://github.com/googleapis/python-genai/issues/1875)) — so for daily-quota (RPD) exhaustion, backoff is pointless. Distinguish: 429 on a per-minute limit → retry; 429 that persists past ~2 min → treat as quota-exhausted, fail the job, tell the user.

## A6. Validating an API key cheaply — plus a deadline you must act on

**Yes, use list-models.** It costs zero tokens and is the canonical cheap probe:

```python
from google import genai
from google.genai import errors

def test_gemini_key(key: str) -> tuple[bool, str]:
    try:
        client = genai.Client(api_key=key)
        models = [m.name for m in client.models.list()]
        return True, f"OK — {len(models)} models available"
    except errors.ClientError as e:
        if e.code in (401, 403):
            return False, "Invalid key, or key lacks API-level restriction (see below)"
        return False, f"Client error {e.code}: {e}"
    except Exception as e:
        return False, f"Unreachable: {e}"
```
`GET /v1beta/models` also gives you **supported functionality and context-window size per model** — use it to populate your model dropdown dynamically instead of hardcoding a list that rots every 8 weeks. ([Models API](https://ai.google.dev/api/models))

### 🚨 The API-key change your settings page must handle

- Header is unchanged: **`x-goog-api-key: <KEY>`**, both key types. **No SDK code changes** — same `genai.Client(api_key=...)`.
- **19 June 2026:** Gemini API began **rejecting standard API keys that lack explicit API-level restrictions**. Keys scoped to "any API" stopped working. ([official forum notice](https://discuss.ai.google.dev/t/action-required-restrict-gemini-api-keys-by-june-19-to-avoid-service-disruption/171786), [Cybernews](https://cybernews.com/security/google-gemini-reject-unrestricted-standard-keys/))
- **September 2026 (weeks away):** *all* standard keys get rejected. You must be on **auth keys** — service-account-backed credentials, Gemini-API-scoped by default, with fast leaked-key enforcement. ([Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key))
- **All new keys created in Google AI Studio are already auth keys.** Root cause of the change: a standard key made for Maps/Firebase could silently become a Gemini credential when someone enabled the API in the same project — a privilege-escalation issue found by Truffle Security.
- **Action:** your "Test connection" error copy for 403 must say *"your key may be an unrestricted standard key — create a new key at aistudio.google.com/api-keys"*, and your docs should tell users to create keys fresh rather than reuse old ones.

### 🚨 Privacy: do not run personal documents through the free tier

[Gemini API Terms](https://ai.google.dev/gemini-api/terms), verbatim:
- Unpaid: *"Google uses the content you submit to the Services and any generated responses to provide, improve, and develop Google products"*; *"human reviewers may read, annotate, and process your API input and output"*; *"Do not submit sensitive, confidential, or personal information to the Unpaid Services."*
- Paid: *"Google doesn't use your prompts (including associated system instructions, cached content, and files such as images, videos, or documents) or responses to improve our products."* Logged only briefly for abuse detection.

Project documents can contain personal data. **Require billing enabled.** Put this in your onboarding text, not buried in a FAQ.

---

# B. Ollama

## B1. Client and REST surface

**`pip install ollama` → v0.6.2, released 2026-04-29** (PyPI, verified). Requires Python ≥3.8; deps `httpx>=0.27`, `pydantic>=2.9`. Note: **not updated since April 2026** while the server ships monthly — the REST API is your stable contract, the Python client is a thin convenience wrapper.

Endpoints ([docs/api.md](https://github.com/ollama/ollama/blob/main/docs/api.md)):

| Endpoint | Method | Use |
|---|---|---|
| `/api/generate` | POST | single-turn completion |
| `/api/chat` | POST | message-list chat (**use this**) |
| `/api/tags` | GET | list installed models ← connection test |
| `/api/ps` | GET | currently loaded-in-memory models |
| `/api/show` | POST | model metadata incl. real context length |
| `/api/version` | GET | server version |
| `/api/embed` | POST | embeddings (newer; `/api/embeddings` is legacy) |
| `/api/pull` `/api/push` `/api/create` `/api/copy` `/api/delete` | | model mgmt |
| `/api/blobs/:digest` | HEAD/POST | blob upload |
| `/v1/*` | | OpenAI-compatible shim |

**Newer additions:**
- **Web search API** — `POST https://ollama.com/api/web_search` (cloud-hosted, needs an API key; max 10 results; generous free tier). Also exposed as tools in the Python/JS libs and as an MCP server. ([blog](https://ollama.com/blog/web-search), [docs](https://docs.ollama.com/capabilities/web-search))
- **Cloud models** — see B3.
- Docs moved to **`docs.ollama.com`** (the old `github.com/ollama/ollama/docs/api.md` still exists but the new site is canonical).

## B2. Structured output — current, and it's good

Confirmed current ([docs.ollama.com/capabilities/structured-outputs](https://docs.ollama.com/capabilities/structured-outputs)). Pass a JSON Schema object to `format`. (`format: "json"` as a bare string is the older, weaker "JSON mode" — schema-less. Use the schema.)

```json
POST http://localhost:11434/api/chat
{
  "model": "qwen3.5:9b",
  "messages": [{"role": "user", "content": "Extract projects. Schema: {...}"}],
  "stream": false,
  "format": {
    "type": "object",
    "properties": {
      "projects": {"type": "array", "items": {
        "type": "object",
        "properties": {"project_name": {"type": "string"},
                       "technologies": {"type": "array", "items": {"type": "string"}}},
        "required": ["project_name"]
      }}
    },
    "required": ["projects"]
  },
  "options": {"temperature": 0, "num_ctx": 32768}
}
```

Python:
```python
from ollama import Client
from pydantic import BaseModel

client = Client(host="http://localhost:11434")
resp = client.chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": prompt}],
    format=Extraction.model_json_schema(),
    options={"temperature": 0, "num_ctx": 32768},
)
data = Extraction.model_validate_json(resp.message.content)
```

**Official best practices:** set `temperature: 0`; **also paste the JSON schema into the prompt text** ("to ground the model's understanding") — the docs explicitly recommend this belt-and-braces approach, and it materially helps small models. Vision models accept the same `format`.

**Failure modes when a model ignores the schema:**
- Ollama uses grammar-constrained decoding, so output is *usually* schema-shaped. What breaks is **semantics**: correct types, garbage values — hallucinated project names, dates like `"2020-13-45"`, empty arrays when data exists. Your Pydantic validation passes; your data is wrong.
- **Endless/repeating output** — the classic failure. A weak model gets stuck emitting `{"projects": [{"project_name": "", ...` filler until it hits `num_predict`. Always set `num_predict`.
- **`$ref` ordering bugs** — Ollama has a real history here ([#8444](https://github.com/ollama/ollama/issues/8444), [#8063](https://github.com/ollama/ollama/issues/8063), [#13184](https://github.com/ollama/ollama/issues/13184)). **Inline your schema; avoid `$defs`/`$ref`.** Pydantic emits `$defs` by default for nested models — flatten deliberately.
- **`oneOf` unsupported on the cloud endpoint** → HTTP 400 ([#13967](https://github.com/ollama/ollama/issues/13967)). Works locally. Avoid `oneOf`/`allOf` entirely for portability.
- **gpt-oss specifically** has documented structured-output problems ([writeup](https://www.glukhov.org/post/2025/10/ollama-gpt-oss-structured-output-issues/)) — don't pick it for this.

## B3. Ollama Cloud — exists, **but cannot do what you need**

Your premise is **correct** on the mechanics:

| | Value |
|---|---|
| Base URL | **`https://ollama.com/api`** (e.g. `/api/chat`, `/api/generate`) |
| Auth header | **`Authorization: Bearer $OLLAMA_API_KEY`** |
| Key creation | `ollama.com/settings/keys`; keys **never expire**, revocable |
| Local auth | **none required** on `http://localhost:11434` |
| CLI login | `ollama signin` — after that local Ollama transparently proxies `*-cloud` models |
| Naming | `-cloud` suffix: `gpt-oss:120b-cloud`, `qwen3.5:397b-cloud`, `deepseek-v3.1:671b-cloud` |
| Data | *"Ollama's cloud does not retain your data"* |

([Authentication docs](https://docs.ollama.com/api/authentication), [Cloud docs](https://docs.ollama.com/cloud), [Cloud models blog](https://ollama.com/blog/cloud-models))

**Cloud model catalogue** (from [ollama.com/search?c=cloud](https://ollama.com/search?c=cloud)): `deepseek-v4-flash` (284B MoE/13B active, 1M ctx), `deepseek-v4-pro`, `kimi-k3`, `kimi-k2.7-code`, `kimi-k2.6`, `glm-5.1`, `glm-5.2`, `minimax-m2.7`, `minimax-m3` (1M ctx), `nemotron-3-ultra`, `nemotron-3-super` (120B MoE/12B active), `nemotron-3-nano`, `qwen3.5` (to 397b-cloud), `gemma4` (to 31b), `mistral-large-3`, `gpt-oss:20b/120b`.

**Pricing** (third-party, **UNVERIFIED** against an official page): Free (1 cloud model, light use, unlimited local), **Pro $20/mo** (3 cloud models, ~50× usage, private models), **Max $100–200/mo** (10 cloud models). Metered by model + tokens with "difficulty levels" 1–4 rather than a flat token cap. ([hackup](https://hackup.ai/ai-plans/ollama/), [pooyagolchian](https://pooyagolchian.com/blog/ollama-cloud-pricing-hardware-requirements-2026/))

### 🚨 The blocker

> **"Ollama's Cloud currently does not support structured outputs."** — [docs.ollama.com/capabilities/structured-outputs](https://docs.ollama.com/capabilities/structured-outputs), also in the [repo source](https://github.com/ollama/ollama/blob/main/docs/capabilities/structured-outputs.mdx)

Corroborated by open issues: [#13206 "Structured output request don't work in Cloud's Qwen3-coder"](https://github.com/ollama/ollama/issues/13206) and [#13967 (cloud JSON-schema parser rejects `oneOf`)](https://github.com/ollama/ollama/issues/13967).

**Consequence for your design:** the Ollama provider is **local-only** for extraction. Don't build an Ollama Cloud config path for this feature — you'd ship a silently-broken option. If you want a hosted open-weights fallback, use an OpenAI-compatible provider that *does* enforce schemas, not Ollama Cloud.

## B4. Local models for structured extraction — and where they'll disappoint

Realistic laptop tiers (sizes verified from ollama.com library pages):

| Tier | Model | Download | Native ctx | Notes |
|---|---|---|---|---|
| 8 GB VRAM / 16 GB RAM | **`qwen3.5:4b`** | 3.4 GB | 256K | best size/quality ratio for JSON extraction |
| | `qwen3.5:2b` | 2.7 GB | 256K | fast; expect field misses |
| | `nemotron-3-nano:4b` | — | — | alternative small instruct model |
| | `gemma4:e2b` | 7.2 GB | 128K | QAT variant available |
| 12–16 GB VRAM | **`qwen3.5:9b`** | 6.6 GB | 256K | ← **my recommendation** for local extraction |
| | `gemma4:12b` | 7.6 GB | 256K | |
| 24 GB VRAM | `qwen3.5:27b` | 17 GB | 256K | genuinely usable quality |
| | `gemma4:26b` / `:31b` | 18 / 20 GB | 256K | |
| 48 GB+ | `qwen3.5:35b` | 24 GB | 256K | |

([qwen3.5](https://ollama.com/library/qwen3.5), [gemma4](https://ollama.com/library/gemma4)). Rule of thumb from community benchmarks: 8 GB VRAM runs a 7–9B at Q4_K_M at ~40 tok/s; **stay at Q4_K_M**; a 14B needs 12 GB. Critically — **KV cache grows with context and is what actually OOMs you**, so raising `num_ctx` for a long document can push a model that "fits" into swap. ([Local AI Master 8GB guide](https://localaimaster.com/vram/best-ollama-models-8gb-vram), [Morph VRAM rankings](https://www.morphllm.com/best-ollama-models))

Note `qwen3.5`'s Ollama page does **not** advertise tool-calling/structured-output capability tags — **UNVERIFIED** whether that's a docs omission. Since Ollama's `format` is enforced by the server's grammar decoder rather than by model-native tool support, it will still produce schema-shaped JSON; quality is the variable.

### Where local will disappoint you — be honest with users

1. **Scanned PDFs.** Dead end. Your local pipeline has no OCR unless you add Tesseract/RapidOCR. Gemini reads them natively. This alone means local can't be your only option.
2. **Multi-column document layouts.** You're feeding local models the *text extractor's* output, so column bleed and interleaved reading order are already baked in. Gemini sees the rendered page. This is the single largest accuracy gap.
3. **Long documents.** A 15-page document is ~8–12k tokens. A 4B model's *effective* attention over 12k tokens is far worse than its 256K nominal window; expect it to extract projects 1–4 well and degrade after. Gemini 3.5 Flash handles the whole thing.
4. **Field discipline.** Small models hallucinate plausible values for absent fields (inventing an `end_date`, guessing a `client` from context) rather than emitting `null`. Mitigations: explicit "use null, never guess" instruction; make every optional field nullable in the schema; **run a second cheap verification pass** asking "which of these values do not literally appear in the source?"
5. **Latency.** Multi-minute on CPU-only. Non-negotiably a background job.
6. **Cost comparison is not close.** A document extraction on `gemini-3.1-flash-lite` costs roughly a tenth of a cent. Local's value is **privacy/offline/air-gap**, not economics. Say so in your UI.

**Position local Ollama as the privacy-mode fallback, with a visible accuracy warning and mandatory human review of the filled form.** Default to Gemini.

## B5. "Test connection" for local Ollama

```python
import httpx

def test_ollama(host: str = "http://localhost:11434", timeout: float = 3.0):
    try:
        with httpx.Client(base_url=host, timeout=timeout) as c:
            ver = c.get("/api/version").json().get("version")
            tags = c.get("/api/tags").json().get("models", [])
        return {
            "ok": True,
            "version": ver,
            "models": [m["name"] for m in tags],   # e.g. "qwen3.5:9b"
            "loaded": None,
        }
    except httpx.ConnectError:
        return {"ok": False, "error": "Ollama not running. Start it or check the host/port."}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Ollama did not respond within 3s."}
```
- `GET /api/version` — cheapest liveness probe.
- `GET /api/tags` — installed models. **Use this to populate the model dropdown**; never hardcode.
- `GET /api/ps` — which models are resident in memory (useful for a "first request will be slow, model is cold" hint).
- `POST /api/show` with `{"model": "..."}` — **read the model's real advertised context length here** and use it to cap `num_ctx` (see B6).
- Remote instances: `OLLAMA_HOST` must be set on the *server* to bind non-localhost. A connection refused from another machine is almost always this, not a firewall.

## B6. `num_ctx` — the silent-truncation trap. Be precise here.

**Official FAQ says: "By default, Ollama uses a context window size of 4096 tokens."** ([docs.ollama.com/faq](https://docs.ollama.com/faq))

**But that's now incomplete.** Ollama **0.15.5** introduced VRAM-tiered dynamic defaults — `OLLAMA_CONTEXT_LENGTH` compiles to `0`, a sentinel meaning "decide at runtime":

| Detected VRAM | Default context |
|---|---|
| < 24 GiB | **4,096** |
| 24–48 GiB | 32,768 |
| ≥ 48 GiB | 262,144 |

Confirmed by [ollama/ollama issue #14073](https://github.com/ollama/ollama/issues/14073), where a user with 52 GB VRAM reports the 262,144 default causing GPU→CPU spillover and unresponsiveness. **The official FAQ has not been updated to reflect this** — treat the FAQ's flat "4096" as the number you'll actually hit on any normal laptop (all consumer GPUs are <24 GiB).

### The bug this causes

Ollama logs `level=WARN msg="truncating input prompt" limit=4096 prompt=10573 keep=4 new=4096` **server-side** and returns a completely normal-looking 200 response. Your app sees valid JSON extracted from the first ~40% of the document and has no idea. ([RepoFold writeup](https://repofold.dev/blog/ollama-silently-truncates-your-prompts), [jangwook experiment](https://jangwook.net/en/blog/en/ollama-num-ctx-silent-truncation-experiment/))

A 15-page document ≈ 10–12k tokens. **Every long document you send at the default is truncated.**

### Three ways to raise it, in order of preference for you

1. **Per request (do this).** `options.num_ctx` on `/api/chat` and `/api/generate`:
   ```python
   options={"num_ctx": 32768, "num_predict": 8192, "temperature": 0}
   ```
2. **Server-wide.** `OLLAMA_CONTEXT_LENGTH=32768 ollama serve` — sets the default for every model. Introduced ~v0.5.13 (March 2025), and **an explicit value overrides the VRAM tier in either direction**.
3. **Baked into the model.** A `Modelfile` with `PARAMETER num_ctx 32768` + `ollama create`. Useful if third-party tooling can't pass options.

### ⚠️ `num_ctx` cannot be set on the OpenAI-compatible `/v1` endpoint

*"the OpenAI-compatible `/v1` endpoint, which is what most SDKs and tooling actually speak, has nowhere to put it."* ([documented as a real bug in openclaw#4028](https://github.com/openclaw/openclaw/issues/4028))

**If you route Ollama through an OpenAI-compatible client (e.g. the `openai` SDK, LiteLLM, LangChain's `ChatOpenAI` pointed at `localhost:11434/v1`) you get silent 4096-token truncation with no way to fix it per-request.** → **Use the native `ollama` Python client / native REST. Do not use the `/v1` shim for this feature.**

### Mandatory guardrails in your code

```python
# 1. Discover the model's real ceiling
info = client.show(model)                       # POST /api/show
model_ctx = info.get("model_info", {}).get("...context_length")  # key is arch-prefixed

# 2. Pre-flight token estimate (chars/3.5 is fine for most documents)
est = len(text) // 3 + 1500       # + prompt/schema overhead

# 3. Choose num_ctx, respecting the model ceiling and VRAM reality
num_ctx = min(max(8192, next_pow2(est)), model_ctx or 32768, 32768)

# 4. VERIFY AFTER THE CALL — this is the actual truncation detector
resp = client.chat(..., options={"num_ctx": num_ctx, "temperature": 0})
if resp.get("prompt_eval_count", 0) < est * 0.85:
    raise TruncationError(
        f"Ollama processed only {resp['prompt_eval_count']} of ~{est} tokens. "
        f"Raise num_ctx or chunk the document."
    )
```
`prompt_eval_count` sitting suspiciously at `num_ctx - 1` is the signature of truncation. **Also chunk long documents** rather than relying on a 256K window — a 4B model's effective recall over 30k tokens is poor regardless of what fits.

---

# C. Python document parsing on Windows (2026)

All versions below verified live from the PyPI JSON API on 2026-08-21, and maintenance status from the GitHub API.

## C1. PDF text extraction

| Library | Version (date) | License | Speed | Table quality | Windows install |
|---|---|---|---|---|---|
| **pypdf** | 6.16.1 (2026-08-14) | **BSD-3-Clause** | slow | weak | pure Python — trivial |
| **pdfplumber** | 0.11.10 (2026-06-15) | **MIT** | ~18 pg/s | **best** | wheels only (`pdfminer.six`, `Pillow`, `pypdfium2`) — trivial |
| **PyMuPDF / pymupdf4llm** | 1.28.2 (2026-08-06) | **AGPL-3.0 or commercial (Artifex)** | ~180 pg/s | good | wheels — trivial |
| **docling** | 2.121.0 (2026-08-20) | **MIT** | slow (ML models) | excellent + layout | heavy: pulls `torch`, `torchvision`, `rapidocr` |

Speed/accuracy figures: [pdfmux benchmark](https://pdfmux.com/blog/pymupdf-vs-pdfplumber/) (PyMuPDF 8–12× faster on plain text: 180 vs 18 pg/s); [PyMuPDF's own comparison](https://pymupdf.readthedocs.io/en/latest/about.html) (8s vs pdfminer's 227s over 7,031 pages).

**The AGPL problem is real.** PyMuPDF is dual-licensed AGPL-3.0 / commercial-Artifex, and **`pymupdf4llm` inherits the same terms.** AGPL's network clause means if your FastAPI backend is reachable by users, you may owe them your source. If this is a commercial product, PyMuPDF is either a license purchase or a no-go. Don't let it into the dependency tree "just for now."

**Also worth knowing:** `docling` moved to `docling-project/docling` under LF AI & Data — **65,335 stars, pushed today, MIT**. It now splits into `docling` (batteries-included) and **`docling-slim`** whose base install is only `pydantic`/`requests`/`tqdm` — the `[standard]` extra is what drags in torch. It parses **PDF, DOCX, HTML, PPTX, XLSX, MD, email** into one document model and uses **`pypdfium2` (BSD/Apache)**, not PyMuPDF. Docs say Windows x86_64 and arm64 are supported; you must pick your own torch distribution. ([Docling install](https://docling-project.github.io/docling/getting_started/installation/))

### ✅ Recommendation: **pdfplumber**

MIT, no native deps, pip-installs clean on Windows, and it's the strongest of the permissive options at exactly the thing many project documents are full of — tables and multi-column layout boxes. You're not processing 7,000-page corpora; 18 pg/s means a 15-page document in under a second. Speed is not your bottleneck; a network call to Gemini is.

Use `pypdf` alongside it only for structural work (page count, encryption detection, splitting). **Skip PyMuPDF** unless you buy a license. **Skip docling for v1** — a 2–3 GB torch install on every developer's Windows laptop for a job Gemini already does better is a bad trade; revisit if you later need fully-offline high-fidelity layout parsing.

Also do a **scanned-PDF check**: if `sum(len(p.extract_text() or "") for p in pdf.pages) < 100`, it's an image scan → force the Gemini path (or refuse in local mode with a clear message).

## C2. `.docx`

**Yes, `python-docx` is still the answer.** v1.2.0 (2025-06-16), MIT, requires Python ≥3.9, 5,695 stars, last pushed 2026-08-01. Mature and maintained-if-not-fast-moving (512 open issues reflects age + scope, not abandonment).

**Does it get headers/footers/tables?**
- **Tables: yes**, fully — `document.tables`, `.rows`, `.cells`, and cells contain paragraphs. Good.
- **Headers/footers: yes, but only since 0.8.11** and only via `section.header` / `section.footer`. Two gotchas: (a) `header.is_linked_to_previous` — you must walk *all* sections and resolve inheritance or you'll silently read empty headers; (b) **`document.paragraphs` does NOT include header/footer content** — the #1 "why is my extraction missing a key detail" bug, because document templates love putting names/titles in the header.
- **Text boxes: NO.** `python-docx` cannot reach content inside `w:txbxContent`. Designer document templates use text boxes heavily. This is a genuine data-loss hole.

**Better options?**
- **`docx2python`** — better at *extraction specifically*: pulls headers, footers, footnotes, endnotes, and text boxes into a structured nested list. **Use it for extraction alongside python-docx.**
- **`mammoth` 1.12.1 (2026-08-09, BSD-2-Clause)** — DOCX → semantic HTML. Actively maintained. **This is directly relevant to you**: since you store rich text as HTML, `mammoth` gives you DOCX-in → HTML-in-your-DB with bold/italic/lists preserved, closing the loop with html-for-docx on the way out.
- **`docling`** also handles DOCX if you go that route.

**Recommendation:** `python-docx` for writing + table access; **`docx2python` for extraction** (headers/footers/textboxes); **`mammoth`** when you want the HTML representation rather than plain text.

## C3. Legacy binary `.doc` on Windows without Word — **reject it**

Blunt assessment of each option:

| Option | Verdict |
|---|---|
| **`antiword`** | **Dead.** The PyPI `antiword` package is v0.1.0 from **2021-10-19** and is only a wrapper — it shells out to the `antiword` C binary, which has no maintained Windows build and hasn't been developed in ~20 years. Not viable. |
| **`textract`** | Deceptive. v2.0.0 shipped 2026-04-27 (after 1.6.5 sat since 2022), so it *looks* revived. But inspect the deps: `pillow, speechrecognition, beautifulsoup4, lxml, chardet, docx2txt, extract-msg, pdfminer-six, python-pptx, xlrd`. **Nothing there handles binary `.doc`** — for `.doc` it still shells out to `antiword`. On Windows, `.doc` fails. It also drags in `speechrecognition` and `pocketsphinx`-adjacent baggage you'd never want. Avoid. |
| **LibreOffice headless** | **The only thing that actually works.** `"C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to docx --outdir <out> <in.doc>`, then parse the .docx. But: a **~700 MB out-of-band install** every user/CI runner needs; `soffice` refuses to run a second instance against the same user profile (must pass `-env:UserInstallation=file:///...` per invocation); it hangs on malformed input, so you need a hard subprocess timeout + kill; and it's another attack surface parsing untrusted files. ([facebook/loutils examples](https://pypi.org/project/loutils), [Cantoni](https://www.cantoni.org/2020/01/15/how-to-convert-word-doc-to-docx-format/)) |
| **`pywin32` / `win32com`** | Requires Microsoft Word installed. Explicitly out of scope, and Windows-only so it can't follow you to Linux. |
| **Spire.Doc** | Handles `.doc` natively with no Office install ([e-iceblue](https://www.e-iceblue.com/Tutorials/Python/Spire.Doc-for-Python/Program-Guide/Document-Operation/read-word-doc-or-docx-files-in-python.html)). **Commercial**, with a free edition that page-limits. Only consider if a paying customer demands `.doc`. |
| **Gemini direct** | `.doc` is **not** an accepted Gemini input type. No shortcut here. |

### ✅ Recommendation: reject `.doc` with a helpful error

```python
LEGACY = {".doc", ".rtf", ".odt", ".pages", ".wpd"}
# on upload:
if ext in LEGACY:
    raise HTTPException(415, detail={
        "code": "legacy_format_unsupported",
        "message": (
            f"{ext} is a legacy format we can't read reliably. "
            "Please open it in Word, Google Docs, or LibreOffice and "
            "save as .docx or export as PDF, then upload again."
        ),
        "accepted": [".pdf", ".docx", ".txt", ".md"],
    })
```
`.doc` has been non-default in Word since **2007** (19 years). Users who have one can convert it in three clicks. The cost of supporting it — a 700 MB dependency, subprocess-hang handling, per-invocation profile isolation, and CI that can't run without it — is wildly out of proportion to the value. Detect it explicitly and give great copy; do not accept-then-fail-later, and do not sniff-as-docx (a `.doc` renamed to `.docx` will blow up inside `python-docx` with an unhelpful zipfile error — check magic bytes: `.docx` is a ZIP starting `PK\x03\x04`; binary `.doc` is OLE2, `D0 CF 11 E0 A1 B1 1A E1`).

## C4. Generating DOCX, and HTML → DOCX

**Generation: `python-docx`** (as above). Companions:
- **`docxtpl` 0.20.2 (2025-11-13, LGPL-2.1)** — Jinja2 templating inside a real .docx you design in Word. **Strongly consider this** for a project-document generator: let designers own the .docx template, you fill placeholders. LGPL is fine for use-as-library.
- **`docxcompose` 2.2.0 (2026-06-02, MIT)** — merge multiple .docx preserving styles/numbering. Useful for per-project sections.

### 🚨 HTML → DOCX: there is a PyPI naming trap. Get this right.

| PyPI name | Version | Date | Reality |
|---|---|---|---|
| `htmldocx` | 0.0.6 | **2021-08-25** | original `pqzx/html2docx` — **abandoned, 5 years stale** |
| `html4docx` | 0.0.3 | **2023-12-08** | **stale squatted-ish name — DO NOT INSTALL** |
| **`html-for-docx`** | **1.2.0** | **2026-08-17** | ✅ **this is the maintained fork** |

The GitHub repo is **[`dfop02/html4docx`](https://github.com/dfop02/html4docx)** (MIT, 64 stars, pushed 2026-08-17, **0 open issues**) but it publishes to PyPI as **`html-for-docx`**. So:

```bash
pip install html-for-docx     # ← correct
```
```python
from docx import Document
from html4docx import HtmlToDocx      # ← import name is html4docx

document = Document("project_template.docx")
parser = HtmlToDocx()
parser.add_html_to_document(project_description_html, document)
document.save("out.docx")
```

**Feature coverage — matches your requirements:**
- ✅ **bold, italic, underline, strikethrough**
- ✅ **ordered and unordered lists, with nesting**
- ✅ tables incl. rowspan/colspan/cell styling
- ✅ images with width/height
- ✅ inline CSS, external stylesheets, and **CSS-class → Word-style mapping** (so you can map your editor's classes onto your template's named styles — very valuable for a project-document generator)
- Accepts an **existing `Document` object** and appends at the end, so you can interleave template content and rich text.

**Documented limitations:**
1. **Ordered lists cap at 3 nesting levels** — deeper collapses to level 3.
2. Complex CSS selectors (child/adjacent-sibling combinators), pseudo-classes, media queries, `@import` are unsupported.
3. Optimized for Microsoft Word; LibreOffice/Google Docs rendering is secondary.

**Maintenance verdict:** actively maintained (pushed today-ish, zero open issues, 20 releases). Small project (64 stars) — pin the version and keep your HTML subset narrow. **Sanitize/normalize your stored HTML to a whitelist** (`p, br, strong, b, em, i, u, s, ul, ol, li, a, table, tr, td, th, h1-h4`) at save time. That both protects against XSS in your web UI and guarantees html-for-docx sees only what it handles.

**Reverse direction:** `mammoth` (DOCX → HTML) for ingest, so the round-trip is symmetric.

## C5. HTML+CSS → PDF: WeasyPrint's Windows story has **not** improved

**WeasyPrint 69.0 (2026-06-02, BSD-3-Clause), 9,520 stars, pushed 2026-08-21 — very actively maintained.** Rendering quality for print CSS (`@page`, margin boxes, running headers, page counters) is the best in the Python ecosystem.

### But: Windows still needs Pango via MSYS2. Confirmed today.

From [WeasyPrint 69.0 "First Steps"](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html):
1. Install Python from the Microsoft Store
2. **Install MSYS2, then `pacman -S mingw-w64-x86_64-pango`**
3. Create a venv, `pip install weasyprint`
4. Ensure the MSYS2 `mingw64/bin` directory is on `PATH` (or set `WEASYPRINT_DLL_DIRECTORIES`) so the DLLs resolve

*"The easiest way to install these libraries is to use MSYS2."* **The docs show no reduction in native dependencies** — Pango (and transitively cairo, GDK-PixBuf, HarfBuzz, GLib, fontconfig) is still required. There's a standalone `.exe` release for CLI use, but that doesn't help you import it as a library in a FastAPI process.

**This is a real onboarding tax:** ~1 GB MSYS2 install, PATH surgery, and the classic `OSError: cannot load library 'libgobject-2.0-0'` that every Windows WeasyPrint user hits. It also complicates CI on `windows-latest`.

### Alternatives

| Option | Assessment |
|---|---|
| **Playwright** 1.62.0 (2026-07-31) | `pip install playwright && playwright install chromium` — **one command, works on Windows, no MSYS2**. Full Chromium fidelity: JS, webfonts, flexbox/grid, and `page.pdf()` supports `@page`, `printBackground`, headers/footers, `preferCSSPageSize`. Cost: ~150 MB browser download; ~300–400 MB heavier Docker images than WeasyPrint's 200–400 MB. Warm performance is excellent (~3 ms for a simple doc). ([PDF4.dev benchmark](https://pdf4.dev/blog/html-to-pdf-benchmark-2026), [python comparison](https://pdf4.dev/blog/generate-pdf-from-html-python)) |
| **`pdfkit` / wkhtmltopdf** | **Dead. Do not use.** wkhtmltopdf was **officially deprecated in 2023**, no maintainers, no arm64 macOS/Linux binaries. Its Chromium is ancient (no flexbox/grid). ([wkhtmltopdf alternatives 2026](https://pdf4.dev/blog/wkhtmltopdf-alternatives-2026)) |
| **`docx2pdf`** | **Abandoned** — 0.1.8 from **2021-12-11**, and it requires Microsoft Word installed. No. |
| **LibreOffice headless** | Works, but 700 MB and mediocre HTML/CSS fidelity. Only if you're already installing it. |
| **Hosted API** (DocRaptor/PDFShift/etc.) | Zero local deps, but sends personal document data to a third party. Same privacy objection as the Gemini free tier. |

### ✅ Recommendation: **Playwright + Chromium for now; keep WeasyPrint as a swappable Linux-prod backend**

Your constraint is explicitly "must work on Windows." Playwright's install is one command on Windows and identical on Linux — the same code deploys unchanged. WeasyPrint is objectively the better *print-CSS* engine and the lighter container, but you pay for it with an MSYS2 prerequisite in every developer's setup guide and every Windows CI run.

**Also note the perf asymmetry:** WeasyPrint can be genuinely slow on complex documents (one benchmark: ~100 s for a 52-page PDF). Playwright is faster once the browser is warm — so **reuse one browser instance across requests** (launch in a FastAPI lifespan handler, `new_page()` per render). Cold-launching Chromium per PDF is the mistake that makes people think Playwright is slow.

Put both behind a `PdfRenderer` protocol with `render(html: str, css: str) -> bytes`. You'll want the option, and your CSS will need per-engine tweaks either way.

---

# D. Job queue on Windows

Versions verified from PyPI/GitHub on 2026-08-21.

## Celery — your premise is *half* right, and the nuance matters

The accurate statement: **Celery never stopped working on Windows; the *prefork pool* did.** Windows has no `fork()`, only spawn, and Celery's `billiard` dependency removed the OS-conditional fork/spawn mechanism — killing prefork (the default pool) on Windows. ([celery.school: Running Celery on Windows](https://celery.school/celery-on-windows), [Concurrency docs](https://docs.celeryq.dev/en/stable/userguide/concurrency/))

What still works on Windows: `--pool=solo` (in-process, concurrency 1), `--pool=threads`, `--pool=gevent` (gevent officially supports Windows), `--pool=eventlet`.

**Celery 5.6.3 (2026-03-26), 28,803 stars, pushed 2026-08-20 — very much alive.** But: **795 open issues**, no first-class async, and the Windows story is "use a non-default pool and hope." The dev/prod behavioural divergence (`solo` locally, `prefork` in prod) is exactly where subtle bugs hide.

## The field

| Library | Version (date) | License | Stars | Pushed | Async-native | Brokers |
|---|---|---|---|---|---|---|
| **Celery** | 5.6.3 (2026-03-26) | BSD-3 | 28,803 | 2026-08-20 | no (sync-first) | RabbitMQ, Redis, SQS, Pub/Sub, Kafka |
| **Dramatiq** | 2.2.0 (2026-06-17) | **LGPL-3.0** | 5,309 | 2026-08-13 | no (sync-first) | RabbitMQ, Redis |
| **ARQ** | 0.28.0 (2026-04-16) | MIT | 3,000 | 2026-04-16 | **yes** | **Redis only** |
| **SAQ** | 0.26.4 (2026-05-21) | MIT | 879 | 2026-08-14 | **yes** | **Redis *or* Postgres** |
| **Taskiq** | 0.12.4 (2026-05-08) | MIT | 2,295 | 2026-08-15 | **yes** | RabbitMQ, Redis, NATS |

Notes: **ARQ moved org to `python-arq/arq`** (Samuel Colvin's, of Pydantic) — 3,000 stars but **last push 2026-04-16**, the slowest cadence of the async three. **Dramatiq is LGPL-3.0** — fine to use as a library, but flag it if your legal team is allergic. A 2026 five-way comparison also covers FastStream and Repid (Repid fastest in their benchmarks) — worth reading if throughput matters, which for document extraction it doesn't. ([aleksul: Choosing a Python task queue library in 2026](https://aleksul.space/posts/choosing-python-task-queue-library/))

**Windows support for ARQ/SAQ/Taskiq: UNVERIFIED against official docs** — none of them documents Windows explicitly. Practically they're pure-Python `asyncio` + a network client, so they run. Two real caveats:
- **`uvloop` is not available on Windows.** Don't unconditionally `uvloop.install()` in worker startup; guard on `sys.platform`.
- Windows uses `ProactorEventLoop` by default on 3.8+. Subprocess handling differs — relevant if a task shells out to `soffice` or Chromium. Test your subprocess timeouts on Windows specifically.

## Redis on Windows

Three options, and **the situation is better than it used to be**:

1. **Memurai** — a native Windows port, now the **official Redis partner for Windows compatibility**. Redis and Memurai (Janea Systems) partner to port new Redis Community Edition releases plus RediSearch/RedisJSON, *"eliminating the need for WSL2 or Docker."* Runs as a Windows service on 6379, ships `memurai-cli.exe`, compatible with Redis 7. ([Redis tutorial](https://redis.io/tutorials/howtos/how-to-run-redis-on-windows-natively-with-memurai/), [Memurai/Redis partnership](https://www.memurai.com/blog/redis-partners-with-memurai), [Businesswire](https://www.businesswire.com/news/home/20241002905636/en/Redis-on-Windows-Redis-Partners-with-Memurai-for-Windows-Compatibility)) — note the Developer edition is free but has license terms for production; check them.
2. **Docker Desktop** — `docker run -p 6379:6379 redis` — what Redis's own [Windows install docs](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/windows/) recommend. Matches prod exactly. Needs Docker Desktop (licensing for larger orgs).
3. **WSL2** — works, but the Windows↔WSL networking edge cases (localhost forwarding, `.wslconfig`, restarts) generate the most "it worked yesterday" support tickets.

## ✅ Recommendation: **SAQ with the Postgres backend**

```bash
pip install "saq[postgres,web]"
```

Reasoning:

1. **It removes Redis from the problem entirely.** You are building a CRUD app with project forms — you already have Postgres. `pip install saq[postgres]` and your Windows dev machine needs **zero additional services**: no Memurai, no Docker Desktop, no WSL2. That is the single biggest win and it's the thing none of the other four give you. ([SAQ](https://github.com/tobymao/saq) — *"built on top of asyncio and redis **or postgres**"*)
2. **Async-native, so it matches FastAPI.** Your task body is `await gemini_call()` / `await ollama_call()` — long I/O waits. No `asyncio.run()`-inside-a-sync-worker contortions, no `nest_asyncio`, and you can share the same async SQLAlchemy session factory and httpx clients.
3. **It's explicitly ARQ-but-better**, per its own README: lower latency (BLMOVE instead of ARQ's 0.5 s poll → sub-5 ms), up to ~8× faster, a **built-in web UI on :8080** for watching queues/workers (genuinely useful for debugging a slow LLM job), heartbeat monitoring for abandoned jobs, and stuck-job recovery with stack traces.
4. **Cron jobs included** (`CronJob`) — you'll want this for cleaning up expired Gemini Files API uploads and orphaned temp files.
5. **Maintained:** pushed 2026-08-14, **0 open issues**, MIT.
6. **Identical on Linux.** Same code, same backend, same worker command. If you later need Redis for throughput, it's a config change, not a rewrite.

**Trade-off, stated honestly:** 879 stars vs Celery's 28,803. Smaller community, fewer Stack Overflow answers, one primary maintainer. Mitigate by keeping task functions as **thin wrappers around plain async service functions** — `async def extract_document_task(ctx, doc_id)` that does nothing but `await ExtractionService().run(doc_id)`. Then swapping to Taskiq/ARQ/Celery later is a day's work, and your business logic is directly unit-testable with no queue at all.

**Runner-up: Taskiq** — larger community (2,295 stars), more brokers, actively pushed, and has first-class FastAPI dependency-injection integration. Pick it over SAQ if you know you'll need RabbitMQ/NATS, or if the DI integration matters more to you than dropping the Redis dependency.

**Do not pick Celery** for this. Windows means a non-default pool, sync-first means awkward async LLM calls, and you get zero benefit from its scale features at your volume.

**Also: don't use FastAPI `BackgroundTasks`** for LLM extraction. It runs in the same process, dies with the worker on reload/deploy, has no retries, no visibility, and no result store. It's for fire-and-forget emails. ([FastAPI background tasks in 2026](https://blog.rajpoot.dev/posts/fastapi/fastapi-background-tasks-2026/))

---

## Consolidated dependency set

```
# LLM providers
google-genai>=2.19,<3.0          # PIN <3.0 — AFC breaking changes coming
ollama==0.6.2                    # native client; do NOT use the /v1 OpenAI shim

# Document ingest
pdfplumber>=0.11.10              # MIT, no native deps, best permissive table handling
pypdf>=6.16                      # BSD-3, structural PDF ops + page count
docx2python                      # extraction: headers, footers, footnotes, TEXT BOXES
python-docx>=1.2.0               # MIT, tables + generation
mammoth>=1.12.1                  # DOCX -> HTML (round-trips your rich-text storage)

# Document output
html-for-docx>=1.2.0             # NOT html4docx / htmldocx (both stale). import html4docx
docxtpl>=0.20.2                  # optional: Jinja2 templating in a designer-owned .docx
playwright>=1.62                 # HTML+CSS -> PDF; one-command Windows install

# Queue
saq[postgres,web]>=0.26.4        # no Redis needed on Windows dev

# Explicitly excluded
# pymupdf / pymupdf4llm  -> AGPL-3.0 (inherited by pymupdf4llm)
# weasyprint             -> requires MSYS2 + Pango on Windows (still, as of 69.0)
# textract, antiword     -> .doc path is broken on Windows regardless
# docx2pdf               -> abandoned 2021 + requires Word
# pdfkit / wkhtmltopdf   -> wkhtmltopdf deprecated 2023
# google-generativeai    -> EOL 2025-11-30
# celery                 -> prefork pool dead on Windows; sync-first
```

## Action items, ordered by urgency

1. **This month — Gemini auth keys.** Standard API keys stop working in **September 2026**. Create auth keys in AI Studio; make your settings page's 403 message say so explicitly.
2. **Before any real data — enable billing.** The free tier trains on inputs and human reviewers may read them. Project documents can contain PII.
3. **Drop the Ollama Cloud extraction path.** Ollama Cloud does not support structured outputs. Local-only for the Ollama provider.
4. **Set `num_ctx` explicitly on every Ollama call**, use the native client not `/v1`, and assert `prompt_eval_count` post-call. Otherwise you ship silent truncation.
5. **Check `finish_reason == "MAX_TOKENS"` on every Gemini call.** With structured output, hitting the limit yields `None`, not an exception — and thinking tokens count against it.
6. **Strip `temperature`/`top_p`/`top_k`** from Gemini 3.x configs; use `thinking_level="low"` for extraction.
7. **Reject `.doc` at upload** with the copy above. Check magic bytes, don't trust the extension.
8. `pip install html-for-docx`, not `html4docx`.

### Marked UNVERIFIED
- Exact free-tier RPM/TPM/RPD numbers (Google stopped publishing tables; read `aistudio.google.com/rate-limit`)
- Ollama Cloud pricing tiers (third-party sources only)
- Whether Pro models are free-tier-excluded since 2026-04-01
- The complete list of unsupported JSON Schema keywords in Gemini
- Explicit Windows support statements for ARQ/SAQ/Taskiq (none document it; they should work)
- Whether `qwen3.5`'s missing tool-calling capability tag on ollama.com is meaningful or a docs omission

---

### Critical Files for Implementation
No codebase exists yet. These are the files this research says to create first, in dependency order:

- `C:\Users\BS23-DESKTOP-00038\Projects\AIProjectManagement\app\providers\base.py` — `LLMProvider` protocol: `extract(schema, document) -> dict`, `rewrite_field(text) -> str`, `test_connection() -> ConnectionStatus`. Everything above hangs off getting this seam right.
- `C:\Users\BS23-DESKTOP-00038\Projects\AIProjectManagement\app\providers\gemini.py` — `google-genai<3.0`; `response_mime_type` + `response_json_schema`; no temperature/top_p/top_k; `thinking_level="low"`; direct-PDF via Files API; `finish_reason` check; `ClientError.code` mapping; `client.models.list()` for connection test.
- `C:\Users\BS23-DESKTOP-00038\Projects\AIProjectManagement\app\providers\ollama.py` — native `ollama` client only; explicit `num_ctx` + `num_predict` + `temperature=0`; inlined (no `$ref`) schema; `prompt_eval_count` truncation assertion; `/api/version` + `/api/tags` connection test. Local-only.
- `C:\Users\BS23-DESKTOP-00038\Projects\AIProjectManagement\app\ingest\extract.py` — magic-byte format detection, `.doc` rejection, pdfplumber + docx2python + mammoth, scanned-PDF detection, returns `{raw_bytes, mime, extracted_text, page_count, is_scanned}`.
- `C:\Users\BS23-DESKTOP-00038\Projects\AIProjectManagement\app\render\` — `docx.py` (python-docx + html-for-docx) and `pdf.py` (`PdfRenderer` protocol, Playwright backend with a lifespan-shared browser, WeasyPrint backend behind a flag).

**Sources:** [Gemini API libraries](https://ai.google.dev/gemini-api/docs/libraries) · [deprecated-generative-ai-python](https://github.com/google-gemini/deprecated-generative-ai-python) · [python-genai](https://github.com/googleapis/python-genai) · [Gemini models](https://ai.google.dev/gemini-api/docs/models) · [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) · [Structured outputs blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-structured-outputs/) · [Document processing](https://ai.google.dev/gemini-api/docs/document-processing) · [Files API](https://ai.google.dev/gemini-api/docs/files) · [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key) · [Restrict keys by June 19](https://discuss.ai.google.dev/t/action-required-restrict-gemini-api-keys-by-june-19-to-avoid-service-disruption/171786) · [Gemini API terms](https://ai.google.dev/gemini-api/terms) · [Interactions API overview](https://ai.google.dev/gemini-api/docs/interactions-overview) · [Interactions GA blog](https://blog.google/innovation-and-ai/technology/developers-tools/interactions-api-general-availability/) · [Migrate to Interactions](https://ai.google.dev/gemini-api/docs/migrate-to-interactions) · [What's new in 3.7 Flash](https://ai.google.dev/gemini-api/docs/latest-model) · [python-genai #1039](https://github.com/googleapis/python-genai/issues/1039) · [python-genai #782](https://github.com/googleapis/python-genai/issues/782) · [python-genai #1875](https://github.com/googleapis/python-genai/issues/1875) · [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) · [Ollama authentication](https://docs.ollama.com/api/authentication) · [Ollama Cloud](https://docs.ollama.com/cloud) · [Cloud models blog](https://ollama.com/blog/cloud-models) · [Ollama FAQ](https://docs.ollama.com/faq) · [Ollama API reference](https://github.com/ollama/ollama/blob/main/docs/api.md) · [ollama #14073](https://github.com/ollama/ollama/issues/14073) · [ollama #13206](https://github.com/ollama/ollama/issues/13206) · [ollama #13967](https://github.com/ollama/ollama/issues/13967) · [openclaw #4028](https://github.com/openclaw/openclaw/issues/4028) · [Ollama silent truncation](https://repofold.dev/blog/ollama-silently-truncates-your-prompts) · [qwen3.5 library](https://ollama.com/library/qwen3.5) · [gemma4 library](https://ollama.com/library/gemma4) · [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html) · [pdfmux benchmark](https://pdfmux.com/blog/pymupdf-vs-pdfplumber/) · [Docling install](https://docling-project.github.io/docling/getting_started/installation/) · [html4docx repo](https://github.com/dfop02/html4docx) · [WeasyPrint first steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) · [PDF4.dev HTML→PDF benchmark](https://pdf4.dev/blog/html-to-pdf-benchmark-2026) · [wkhtmltopdf alternatives](https://pdf4.dev/blog/wkhtmltopdf-alternatives-2026) · [Celery on Windows](https://celery.school/celery-on-windows) · [Celery concurrency](https://docs.celeryq.dev/en/stable/userguide/concurrency/) · [SAQ](https://github.com/tobymao/saq) · [Task queue comparison 2026](https://aleksul.space/posts/choosing-python-task-queue-library/) · [Redis on Windows with Memurai](https://redis.io/tutorials/howtos/how-to-run-redis-on-windows-natively-with-memurai/) · [Redis–Memurai partnership](https://www.memurai.com/blog/redis-partners-with-memurai)