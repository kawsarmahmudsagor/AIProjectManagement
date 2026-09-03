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

When a document is uploaded, it's parsed and an AI provider (Gemini or OpenAI, whichever
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

Users configure Gemini and/or OpenAI here: an API key for whichever provider they want to
use, pick a default model, and mark one provider as the default used across the app unless
overridden per-request. A "Test connection" button confirms the configuration actually
works before relying on it.

## Tasks

Every project has its own task list, reachable from the project page. Tasks can be added by
hand or created via the AI work breakdown below; each has a title, an optional description, a
status (To do / In progress / Blocked / Done), a priority (Low/Medium/High/Urgent), an optional
due date, and an optional time estimate. A task can have one level of subtasks — a subtask
cannot itself have subtasks. There is no team/assignee concept: tasks belong to the user who
created the project, the same as everything else in this app.

## AI work breakdown

From a project's task list, a user can start a breakdown: upload a spec/document, or just
describe the work in their own words (or both). The AI proposes a list of tasks — and,
sometimes, a task with a few subtasks — for the user to review. Nothing is created until the
user explicitly accepts; proposals can be edited (title, description, priority, time estimate)
before accepting, accepted individually or all at once, or rejected. Each proposed task is
marked either grounded (the AI can point to the exact line in the document it came from) or a
suggestion (a reasonable addition the document doesn't explicitly state) — suggestions are shown
separately and are never pre-selected. The AI never invents a fact (a name, date, deadline,
budget, or specific technology) that isn't in the source, and it never assigns a due date itself.
Tasks created this way are marked with an "AI" badge so they stay visually distinguishable from
tasks added by hand.

**In chat:** a user can also ask Jarvis directly, e.g. "break down building a login page
into tasks for the Billing project" — Jarvis drafts the same kind of proposal from the
description given in the conversation (it has no way to attach a document to a chat
message, so document-based breakdown still needs the project's task page) and lists the
proposed tasks back in the chat. It never creates anything until the user says which ones
to keep (or "all") — only after that confirmation does Jarvis actually create the Task
rows.

## Export

A saved project can be exported as a PDF or a DOCX file from its detail page, preserving
formatting (bold/italic/underline, bullet and numbered lists) from the rich-text fields.

## Jarvis (the chatbot)

Jarvis is the assistant this conversation is happening in. It can: answer questions about
the user's own projects and work history (grounded only in their actual saved project
data — never invented), answer questions about the user's tasks (what's left to do,
what's blocked or overdue, a workload summary — grounded only in their actual saved
tasks), analyze patterns across the user's projects (which technologies they use most,
which projects share a given technology, timelines, roles), recommend real, currently
well-maintained open-source GitHub repositories when asked a general technology question
that isn't about the user's own data, and explain how any feature of this platform works
(using this very reference document). Jarvis can also run the AI work breakdown and Brag
Document Generator features described above, right from the conversation — see the "in
chat" note at the end of each of those two sections. Outside of those two flows, Jarvis
cannot create, edit, or delete a task or project itself — it can only look things up and
talk about them; any other change still has to be made by the user directly in the app.
In Settings > Chatbot, a user
can choose which AI provider (Gemini or OpenAI) drives Jarvis, and can turn on
"Preemptive suggestions" — when enabled, Jarvis may proactively mention a relevant GitHub
repo during a conversation even if not explicitly asked (and a background process also
starts proactively computing repo suggestions for the Dashboard — see "Dashboard —
Suggested for you" below); when off, Jarvis only searches GitHub when explicitly asked to
recommend something, and no dashboard suggestions are computed either. However the toggle
is set, Jarvis never suggests the same GitHub repo to the same user twice — once a repo
has been suggested to a user, in chat or on the Dashboard, it won't be offered to them
again. Jarvis greets the user by name (their preferred name, or first name if none is set)
at the start of a new conversation only — it doesn't repeat the greeting every time the
chat panel is reopened on an existing conversation. Very long conversations are
automatically summarized in the background from time to time so Jarvis can keep track of
earlier context without it consuming so much space that it crowds out the current
question — nothing is removed from the conversation the user sees, only from what's
replayed back to the AI. A conversation's title is also generated automatically from its
first exchange, once there's enough content to summarize.

## Conversations page

The Conversations page, reachable from the sidebar, has two tabs. The "Conversations" tab
lists every past conversation with Jarvis — a user can search by title, filter to only
starred ones, sort by most/least recent, star or unstar a conversation, delete one, or
click one to resume it (resuming opens the floating chat widget on that conversation
rather than whatever it was last showing). The "Suggestions" tab lists every GitHub repo
suggestion this user has ever been given, from either source (the Dashboard's background
computation or something Jarvis surfaced in chat), most recent first, including ones
already dismissed (shown greyed out with a "Dismissed" label) — this is the full history,
unlike the Dashboard card described below. A suggestion can be dismissed from either the
Conversations page or the Dashboard card; either one is the same durable action; a repo
dismissed on one never reappears on the other. The Dashboard also shows a short list of
the most recent conversations as a shortcut into this page's Conversations tab.

## Dashboard — Suggested for you

When "Preemptive suggestions" (Settings > Chatbot) is on, a background process
periodically looks at which technologies appear most across a user's saved projects and
looks up real, currently well-maintained GitHub repositories for the top few — the same
quality bar (minimum stars, not archived, recently active) that Jarvis's own GitHub search
uses. Generic, foundational stack entries (a programming language, a base framework, a
plain database, bare "Unity"/"Unreal", ...) are deliberately excluded from this — the
computation looks for a user's more specific or notable technologies (an LLM/RAG
framework, a named engine plugin, and similar) rather than repeating back whatever
language or framework the user happens to use on every project. These show up as a
"Suggested for you" card on the Dashboard, without the user needing to ask Jarvis
anything. Recomputation happens automatically whenever a project's technologies change,
and periodically in the background otherwise, so the list stays current as a user's
portfolio grows. The Dashboard card only shows suggestions from roughly the last day, so
it doesn't keep accumulating forever — see the Conversations page's Suggestions tab above
for the complete history. Each suggestion can be dismissed from either place; a dismissed
suggestion never reappears, and — per the no-repeat rule above — neither does any repo
already suggested to that user anywhere, whether on this card, the Suggestions tab, or in
chat.

## Brag Document Generator

A dedicated page where a user uploads their team's weekly standup Excel workbook (the
spreadsheet used to track daily Done/Plan/Blocker/Delivery entries) and gets back a
formatted monthly "brag document" — the performance report submitted for that user's own
work. The flow: upload the `.xlsx` file, confirm which row in the sheet is theirs (the app
auto-matches by name and pre-fills it, but a dropdown of every name found in the sheet is
always available if the auto-match is wrong or unconfident) and which month to generate,
then generate. Behind the scenes this combines two sources: the raw work log parsed from
the spreadsheet (the primary source of truth for what was actually done) and that user's
own saved Project responsibilities/description text and completed Tasks for that month
(used only for terminology and clarity, never as a separate source of new facts) — an AI
provider drafts the document's prose from both. The AI never invents an accomplishment
that isn't in the work log or in the user's own project text, and it never states an hour
count or a date in a bullet — all hour/date arithmetic (total logged hours, target hours,
holidays, leave, balance) is computed deterministically from the spreadsheet, never by the
AI, and is shown separately as an hour-stats summary. Work is grouped under Technical
Contribution by project/initiative: a match against one of the user's own saved Projects
uses that project's exact name, but work that isn't one of the user's saved Projects still
gets its own named group (taken from what the work log itself identifies it as) rather
than being lumped together — "On Demand / Miscellaneous" is reserved strictly for a
genuine one-off item with no identifiable project or initiative name in the log at all,
not a catch-all for anything outside the saved project list. Each project's write-up can
include a few named sub-themes (e.g. "RAG Implementation") when its logged work spans more
than one, and a short "Key Contribution" synthesis line summarizing that project's value
for the month. When the month's work spans more than one recognizable discipline (e.g.
MLOps, RAG, Voice AI), an additional Overall Impact section summarizes across them. The
generated document's sections are: Technical Contribution (grouped as above), Overall
Impact (when applicable), Team Support & Collaboration, and Learning & Development — each
section also has a copy-to-clipboard button. The finished document can be downloaded as
DOCX or PDF. Every generated document is automatically saved — there's no separate save
step — under the name "{month} Brag Document" (e.g. "August 2026 Brag Document"), and the
Brag Documents page's main view is a list of every document a user has ever generated,
most recent first, each showing its name, the row it was generated for, and its status;
opening one from that list shows the exact same result view as right after generating it,
including the DOCX/PDF download links.

**In chat:** a user can also ask Jarvis to generate a brag document directly in the
conversation. The `.xlsx` upload itself still has to happen through the Brag Documents
page first (chat has no file-attachment mechanism) — once it's uploaded, Jarvis can find
it, auto-detect (or ask which) row and month, generate the document, and show the drafted
sections and exact hour-stats numbers right in the chat. Jarvis cannot hand over a DOCX/PDF
file in chat, so for the download it points the user to the Brag Documents page to open
that same generated document — which, like every generated document, is already saved and
will also show up in that page's list.

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
