<!--
Update this file in the same PR that ships or changes a user-facing feature. This is
Jarvis's (the chatbot's) ONLY source of truth about what the platform does — it is never
generated from README.md or DESIGN.md, and it is never auto-synced. If a feature described
here changes and this file isn't updated, Jarvis will describe stale or wrong behavior.
-->

## Adding a project

Projects can be added by filling out a form by hand, or by uploading a project document
(PDF, DOCX, or TXT) and letting AI extract a structured entry from it. Uploading is never
required — manual entry is always available. `.doc` (legacy binary Word format) is
rejected at upload; users are asked to save as `.docx` or PDF instead.

## AI extraction from an uploaded document

When a document is uploaded, it's parsed and an AI provider (Gemini or Ollama, whichever
the user has configured) extracts project fields from it: name, role, dates, description,
responsibilities, and technologies. Extraction only fills fields the user hasn't already
typed into — it never overwrites something the user wrote by hand. Extracted fields are
visually marked and can be reverted to the original extracted value at any time. AI never
invents a fact, date, or technology that isn't in the source document — if something isn't
in the document, the field is left blank for the user to fill in.

## Enhance with AI / Generate from long

Within the project form, each text field (Description, Responsibilities — both a long
form and a short summary) has an "Enhance with AI" button that rewrites the existing text
to be clearer, and the short-summary fields also have a "Generate from long" button that
drafts a short summary from the long-form text. In both cases, the AI's suggestion is
never written directly into the field — it appears in a suggestion panel with
Replace / Insert below / Copy / Try again / Discard actions, so the user always explicitly
accepts or discards it.

## Agent Persona (Settings > AI Providers)

A per-user setting with two options: "Business Analyst" (the default) and "Technical
Developer". This changes *how* AI-written text is phrased — Business Analyst frames work
in plain, business-outcome language; Technical Developer names the actual architecture,
languages, and technical approach. It never changes *what* facts the AI is allowed to
state — both personas follow the same "never invent a fact" rule.

## AI Provider settings (Settings > AI Providers)

Users configure Gemini and/or Ollama here: an API key (Gemini) or a base URL (Ollama,
defaults to a local install), pick a default model, and mark one provider as the default
used across the app unless overridden per-request. A "Test connection" button confirms the
configuration actually works before relying on it. Ollama is local-only for document
extraction (Ollama Cloud doesn't support the structured output extraction needs); it works
fine for chat regardless of whether it's local or cloud-hosted.

## Export

A saved project can be exported as a PDF or a DOCX file from its detail page, preserving
formatting (bold/italic/underline, bullet and numbered lists) from the rich-text fields.

## Jarvis (the chatbot)

Jarvis is the assistant this conversation is happening in. It can: answer questions about
the user's own projects and work history (grounded only in their actual saved project
data — never invented), analyze patterns across the user's projects (which technologies
they use most, which projects share a given technology, timelines, roles), recommend
real, currently well-maintained open-source GitHub repositories when asked a general
technology question that isn't about the user's own data, and explain how any feature of
this platform works (using this very reference document). In Settings > Chatbot, a user
can choose which AI provider (Gemini or Ollama) drives Jarvis, and can turn on
"Preemptive suggestions" — when enabled, Jarvis may proactively mention a relevant GitHub
repo during a conversation even if not explicitly asked; when off, it only searches GitHub
when explicitly asked to recommend something. Jarvis greets the user by name (their
preferred name, or first name if none is set) at the start of a new conversation only —
it doesn't repeat the greeting every time the chat panel is reopened on an existing
conversation.

## Profile page

A separate page (not a Settings page) where a user can optionally fill in a photo, their
name details, designation, team, organization, a speciality, primary/secondary skills, and
a few short bio sections (Professional Biography, Work Experience Summary, Career
Objective, Key Strengths, Responsibilities) — each with its own "Enhance with AI" button
that works the same suggest-then-accept way as the project form's fields. Every field on
this page is entirely optional; leaving it blank doesn't limit or degrade any other part
of the app, including Jarvis. When filled in, Jarvis may use it as soft context to bias
which GitHub repos it recommends — it never treats profile content as a verified fact
about the user's project history, and it never mentions profile details in its greeting.
