# Frontend Architecture — AI Project Management Platform

Everything below is verified against the ecosystem as of **August 2026** (searches at the end). Where 2026 changed something that older tutorials still get wrong, I've flagged it — most importantly: **`middleware.ts` is deprecated and renamed to `proxy.ts` in Next.js 16**, and **shadcn/ui's default primitive layer is now Base UI, not Radix**.

---

## 1. Stack — one recommendation per decision

| Concern | Decision | Why |
|---|---|---|
| Framework | **Next.js 16.3.x**, App Router, TypeScript strict, Turbopack | 16.3 is current stable (Aug 2026); Turbopack is stable and default; `middleware`→`proxy` rename lands here |
| React | **React 19.2** (shipped with Next 16) | `useOptimistic`, `useActionState`, `Activity` available |
| Styling | **Tailwind CSS v4.3.x** (CSS-first `@theme`, no `tailwind.config.js`) | v4.2 is already EOL (May 2026); 4.3.3 is the supported line |
| Components | **shadcn/ui on Base UI** (`npx shadcn create`, pick Base UI) | Base UI became shadcn's default in July 2026, is at 1.6.x, and ships **Combobox / Autocomplete / Number Field** which Radix never had. Radix isn't deprecated but new projects should not start there. |
| Icons | **lucide-react** | shadcn's default; has `Sparkles`, `Wand2`, `Calendar`, `Bold`, `List`, `ListOrdered`, `RemoveFormatting` — the exact mockup icon set |
| Rich text | **Tiptap 3.30.x** (`@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-character-count`) | Actively released, MIT. Toolbar (Paragraph dropdown, B/I/U, both lists, clear formatting) is StarterKit + `Underline`. No Tiptap Platform subscription needed |
| Forms | **React Hook Form 7.84.x** + **Zod 4** via `@hookform/resolvers` v5 | Smallest, best inference, native shadcn `<Form>` integration. **Pin to 7.x — do not use `react-hook-form@8.0.0-beta`** |
| Server state | **TanStack Query v5** | `refetchInterval` as a *function* is purpose-built for the job-polling loop; pauses on tab blur by default |
| Date picker | **`@daypicker/react` v10** wrapped in shadcn `Calendar` + `Popover` | Package **renamed** from `react-day-picker` → `@daypicker/react` |
| Date math/format | **date-fns v4** | `format(d, "MMMM do, yyyy")` → exactly "August 21st, 2026" |
| API client | **`@hey-api/openapi-ts`** with `@tanstack/react-query` plugin | Maintained successor to deprecated `openapi-typescript-codegen`; FastAPI's own docs point here |
| Toasts | **sonner** | shadcn standard; needed for AI failure/retry surfaces |
| Tests | Vitest + Testing Library; Playwright for the upload→poll→prefill E2E | Polling and accept/reject need deterministic E2E coverage |

### The three hard editor questions, answered

**(a) Plaintext cap on rich HTML.** Do *not* validate `html.length`. Two layers:

1. **Hard stop at input time** — `CharacterCount.configure({ limit, mode: 'textSize', textCounter })`. `mode: 'textSize'` counts document *text*, ignoring markup, and once at the limit the extension blocks transactions that grow the doc. Use a grapheme-aware `textCounter` so emoji/combining marks count as 1.
2. **Source of truth for validation** — every rich field's form value is a **pair**, not a string:

```ts
// lib/rich-text/types.ts
export type RichText = { html: string; text: string }; // text = editor.getText({ blockSeparator: '\n' })
```

Tiptap produces the plaintext for us, so Zod validates `.text.length` with zero HTML parsing. Backend must recompute `text` from `html` on save and reject mismatches — the client pair is a convenience, not a trust boundary.

Known Tiptap bug to guard: pasting formatted content that overshoots the limit can blank the editor (ueberdosis/tiptap#4820). Mitigate with a `transformPasted`/`handlePaste` guard that truncates the incoming slice's text before it reaches the doc.

```ts
// lib/rich-text/count.ts
const seg = new Intl.Segmenter(undefined, { granularity: 'grapheme' });
export const countPlain = (t: string) => {
  let n = 0; for (const _ of seg.segment(t)) n++; return n;
};
```

**(b) Char counter rendering.** The counter lives *inside* the editor component and reads Tiptap's own store via `useEditorState` with a selector — so it updates on every keystroke without the form (or even the toolbar) re-rendering:

```tsx
const { chars, isBold, isItalic, isUnderline, blockType } = useEditorState({
  editor,
  selector: ({ editor: e }) => ({
    chars: e.storage.characterCount.characters(),
    isBold: e.isActive('bold'),
    isItalic: e.isActive('italic'),
    isUnderline: e.isActive('underline'),
    blockType: e.isActive('heading', { level: 2 }) ? 'h2' : 'paragraph',
  }),
});
```

**(c) Keeping keystrokes out of the form.** Three rules, all enforced by structure:

- Tiptap is the **uncontrolled** owner of the doc. RHF holds a mirror. Value flows *into* the editor only on external events (AI fill, accept suggestion, revert, form reset) — gated by a `revision: number` prop, never by value equality.
- `field.onChange` is called on a **250 ms trailing debounce** (plus immediately on `blur`), so RHF state churns ~4×/sec at worst, not 40.
- Nothing in the parent subscribes to these field values. Form mode is `onTouched` for scalars, and error display uses `useFormState({ control, name })` *inside* each field wrapper, so an error on Short Summary re-renders only that wrapper.

---

## 2. Route & file structure (App Router)

`RSC` = React Server Component (default), `CC` = `'use client'`.

```
src/
├── app/
│   ├── layout.tsx                        RSC  <html class="dark"> · fonts · Providers · Toaster
│   ├── globals.css                            @import "tailwindcss"; @theme { --color-* } dark tokens
│   ├── page.tsx                          RSC  redirect() → /dashboard or /login
│   │
│   ├── (auth)/                                unauthenticated group
│   │   ├── layout.tsx                    RSC  centered card shell; redirects to /dashboard if session
│   │   ├── login/page.tsx                RSC  → <LoginForm/> CC
│   │   ├── register/page.tsx             RSC  → <RegisterForm/> CC
│   │   └── forgot-password/page.tsx      RSC
│   │
│   ├── (app)/                                 authenticated group
│   │   ├── layout.tsx                    RSC  await requireSession() · <AppShell> (sidebar+topbar) · <NavigationBlockerProvider>
│   │   ├── dashboard/
│   │   │   ├── page.tsx                  RSC  prefetch projects → <HydrationBoundary> → <ProjectCardGrid/> CC
│   │   │   ├── loading.tsx               RSC  card skeletons
│   │   │   └── error.tsx                 CC
│   │   ├── projects/
│   │   │   ├── page.tsx                  RSC  the mockup screen: search + inline Add New Project card
│   │   │   ├── loading.tsx
│   │   │   ├── new/page.tsx              RSC  full-page form (deep-link target; same component as inline)
│   │   │   └── [projectId]/
│   │   │       ├── page.tsx              RSC  read-only detail view + Export menu
│   │   │       ├── edit/page.tsx         RSC  prefetch project → <ProjectForm mode="edit">
│   │   │       ├── loading.tsx
│   │   │       └── not-found.tsx         RSC
│   │   └── settings/
│   │       ├── layout.tsx                RSC  settings sub-nav
│   │       ├── page.tsx                  RSC  redirect → ./ai-providers
│   │       ├── ai-providers/page.tsx     RSC  → AgentPersonaSelect CC (business_analyst|technical_developer,
│   │       │                                    PATCH /auth/me) + AiProviderSettings CC (Ollama + Gemini, Test connection)
│   │       └── account/page.tsx          RSC
│   │
│   └── api/                                   BFF — the browser only ever talks to these
│       ├── auth/login/route.ts                POST → FastAPI, sets httpOnly cookies
│       ├── auth/register/route.ts
│       ├── auth/logout/route.ts
│       ├── auth/refresh/route.ts               single-flight refresh
│       ├── auth/session/route.ts               GET current user (client bootstrap)
│       └── bff/[...path]/route.ts               catch-all proxy → FASTAPI_URL, injects Bearer
│
├── proxy.ts                              ← Next 16 name. NOT middleware.ts
│
├── client/                               ← GENERATED by @hey-api/openapi-ts (committed, never edited)
│   ├── types.gen.ts  sdk.gen.ts  @tanstack/react-query.gen.ts  zod.gen.ts
│
├── components/
│   ├── ui/                               shadcn primitives (Base UI): button, input, checkbox, popover,
│   │                                     calendar, tooltip, badge, dialog, alert-dialog, select,
│   │                                     dropdown-menu, skeleton, progress, card, form
│   ├── layout/  app-shell.tsx · sidebar.tsx · topbar.tsx · user-menu.tsx
│   ├── common/  guarded-link.tsx · empty-state.tsx · char-counter.tsx · info-tip.tsx · confirm-dialog.tsx
│   ├── editor/
│   │   ├── rich-text-editor.tsx          CC  Tiptap instance + toolbar + counter (leaf, memoized)
│   │   ├── editor-toolbar.tsx            CC  Paragraph select, B/I/U, OL, UL, clear formatting
│   │   ├── editor-extensions.ts               shared extension factory (limit-aware)
│   │   └── rich-text-field.tsx           CC  RHF <Controller> adapter around the above
│   └── projects/
│       ├── project-search.tsx            CC  "Search projects..." (nuqs-free: useSearchParams + replace)
│       ├── add-project-card.tsx          CC  the expandable card with the × close
│       ├── project-form.tsx              CC  RHF root, single <FormProvider>
│       ├── fields/
│       │   ├── date-range-fields.tsx     CC  Start/End + "Current Project" checkbox
│       │   ├── technologies-field.tsx    CC  input + Add → chips
│       │   ├── project-url-field.tsx     CC
│       │   └── dual-editor-field.tsx     CC  ★ the reusable long/short pair (used 2×)
│       ├── ai/
│       │   ├── upload-dropzone.tsx       CC
│       │   ├── extraction-progress.tsx   CC  job polling UI
│       │   ├── ai-suggestion-panel.tsx   CC  accept / replace / insert / discard
│       │   └── ai-origin-badge.tsx       CC  "AI" chip + Revert
│       ├── project-card.tsx              RSC (presentational)
│       └── export-menu.tsx               CC
│
├── features/
│   ├── projects/  schema.ts · defaults.ts · mappers.ts · queries.ts · use-project-form.ts
│   ├── ai/        use-extraction-job.ts · use-field-suggestion.ts · origin-store.ts
│   ├── auth/      session.ts (server-only) · use-session.ts
│   └── drafts/    use-draft-autosave.ts
├── lib/  api-client.ts · query-client.ts · rich-text/ · utils.ts · env.ts
└── hooks/  use-debounced-callback.ts · use-unsaved-changes-guard.ts
```

**Server/client split rationale:** every `page.tsx` stays an RSC that (1) enforces session, (2) prefetches with a server `QueryClient` and passes a dehydrated state into `<HydrationBoundary>`, (3) renders one client island. Zero interactive logic in RSCs. `app/(app)/layout.tsx` calls `requireSession()` — real authorization lives here and in the BFF route handlers, **not** in `proxy.ts`.

---

## 3. Component tree for Add/Edit Project

```
ProjectsPage (RSC)
└── ProjectsClient (CC)
    ├── ProjectSearch                       ?q= in URL, debounced
    ├── AddProjectCard (collapsible, ×)     ← also rendered standalone by /projects/new
    │   └── ProjectForm  mode="create"|"edit"
    │       ├── FormProvider (RHF)
    │       ├── AiIntakeSection
    │       │   ├── UploadDropzone            PDF/DOC/DOCX/TXT
    │       │   └── ExtractionProgress        polling stages
    │       ├── AiReviewBar                   "5 AI fields to review" · Next · Accept all · Revert all
    │       ├── TextField      name="name"          "Enter project name"
    │       ├── TextField      name="role"          "e.g. Lead Developer"
    │       ├── DateRangeFields
    │       │   ├── DateField  name="startDate"
    │       │   ├── DateField  name="endDate"       disabled+"Present" when isCurrent
    │       │   └── Checkbox   name="isCurrent"     "Current Project"
    │       ├── DualEditorField  ← Project Description
    │       │   ├── SectionHeader + helper text
    │       │   ├── EditorBlock (long)
    │       │   │   ├── LabelRow: Badge "Optional · up to 10,000 chars" + InfoTip + [Enhance long with AI]
    │       │   │   ├── RichTextField → RichTextEditor(EditorToolbar, CharCounter)
    │       │   │   └── AiSuggestionPanel (conditional)
    │       │   └── EditorBlock (short)
    │       │       ├── LabelRow: Badge "Required" + InfoTip + [Generate from long] [Enhance]
    │       │       ├── RichTextField (limit 390)
    │       │       ├── FieldError "Short summary is required"
    │       │       └── AiSuggestionPanel (conditional)
    │       ├── DualEditorField  ← Your Responsibilities  (same component, different props)
    │       ├── TechnologiesField           "e.g. React" + [Add] → chips
    │       ├── ProjectUrlField             "https://..."
    │       └── FormFooter                  [Cancel] [Save Project]
    └── ProjectCardGrid
```

### `DualEditorField` — concrete props contract

```tsx
// components/projects/fields/dual-editor-field.tsx
import type { FieldPath } from 'react-hook-form';
import type { ProjectFormValues } from '@/features/projects/schema';

/** Only paths whose value is RichText are legal here. */
type RichTextPath = Extract<
  FieldPath<ProjectFormValues>,
  `${string}.long` | `${string}.short`
>;

export type AiEnhanceOp = 'enhance-long' | 'generate-short' | 'enhance-short';

export interface DualEditorFieldProps {
  section: 'description' | 'responsibilities';
  title: string;
  helperText: string;

  long: {
    name: RichTextPath;
    label: string;
    badge: string;
    limit: number;
    placeholder: string;
    tooltip: string;
    enhanceLabel: string;
  };

  short: {
    name: RichTextPath;
    label: string;
    badge: string;
    requirement: 'required' | 'recommended';
    limit: number;
    placeholder: string;
    tooltip: string;
    generateLabel: string;
    enhanceLabel: string;
  };

  onRequestAi: (args: {
    op: AiEnhanceOp;
    section: DualEditorFieldProps['section'];
    target: RichText;
    source: RichText;
    signal: AbortSignal;
  }) => Promise<RichText>;

  origin?: Partial<Record<'long' | 'short', FieldOrigin>>;
  onRevertToOriginal?: (slot: 'long' | 'short') => void;

  disabled?: boolean;
  className?: string;
}

export type FieldOrigin =
  | { source: 'user' }
  | { source: 'ai'; jobId: string; original: RichText; edited: boolean };
```

### `RichTextField` — the RHF ↔ Tiptap seam

```tsx
'use client';
export function RichTextField({ name, limit, placeholder, revision }: {
  name: RichTextPath; limit: number; placeholder: string; revision: number;
}) {
  const { field } = useController({ name });
  const commit = useDebouncedCallback((v: RichText) => field.onChange(v), 250);

  return (
    <RichTextEditor
      externalValue={field.value}
      externalRevision={revision}
      limit={limit}
      placeholder={placeholder}
      onChange={commit}
      onBlur={() => { commit.flush(); field.onBlur(); }}
    />
  );
}
```

```tsx
// inside RichTextEditor
const applied = useRef(-1);
useEffect(() => {
  if (externalRevision === applied.current || !editor) return;
  applied.current = externalRevision;
  editor.chain().setContent(externalValue.html, { emitUpdate: false }).run();
}, [externalRevision, editor]);
```

---

## 4. AI interaction UX

### 4.1 Upload → job → prefill

| Stage | UI |
|---|---|
| `idle` | Dashed dropzone: "Drop a PDF, DOC, DOCX or TXT — or fill the form manually". Manual entry always available; AI is never a gate |
| `uploading` | Determinate `<Progress>` from `XMLHttpRequest.upload.onprogress`. Filename + size + Cancel |
| `queued` | "Queued", spinner, elapsed timer |
| `parsing` → `extracting` → `structuring` | 3-step stepper driven by `job.stage`; form stays editable during the wait |
| `succeeded` | Fields fill with staggered highlight; toast; `AiReviewBar` appears with a count |
| `failed` | Inline error mapped from `error.code` (`UNSUPPORTED_FILE`, `NO_TEXT_FOUND`, `PROVIDER_UNREACHABLE`, `RATE_LIMITED`). Retry / Upload different file / Continue manually |
| `timeout` (4 min client-side) | Offer to keep polling or abandon |

`jobId` persists to `localStorage` so a refresh resumes the same poll.

### 4.2 The polling hook

```ts
// features/ai/use-extraction-job.ts
'use client';
type Stage = 'queued' | 'parsing' | 'extracting' | 'structuring';
type Job =
  | { status: 'pending'; stage: Stage; progress?: number }
  | { status: 'succeeded'; result: ExtractionResult }
  | { status: 'failed'; error: { code: string; message: string } };

const MAX_WAIT_MS = 4 * 60_000;

export function useExtractionJob(jobId: string | null) {
  const startedAt = useRef<number>(Date.now());
  const [gaveUp, setGaveUp] = useState(false);

  const query = useQuery({
    queryKey: ['extraction-job', jobId],
    queryFn: ({ signal }) => getExtractionJob({ path: { jobId: jobId! }, signal }),
    enabled: Boolean(jobId) && !gaveUp,
    refetchInterval: (q) => {
      const d = q.state.data as Job | undefined;
      if (!d || d.status !== 'pending') return false;
      if (Date.now() - startedAt.current > MAX_WAIT_MS) { setGaveUp(true); return false; }
      const n = q.state.dataUpdateCount;
      return Math.min(1000 * 1.5 ** n, 5000);
    },
    refetchIntervalInBackground: true,
    staleTime: 0,
    gcTime: 10 * 60_000,
    retry: (count, err) => !isClientError(err) && count < 4,
    retryDelay: (a) => Math.min(1000 * 2 ** a, 8000),
  });

  const job = query.data as Job | undefined;
  return {
    job,
    stage: job?.status === 'pending' ? job.stage : undefined,
    elapsedMs: Date.now() - startedAt.current,
    isPolling: query.isFetching || job?.status === 'pending',
    timedOut: gaveUp,
    retry: () => { startedAt.current = Date.now(); setGaveUp(false); query.refetch(); },
  };
}
```

On `succeeded`, apply into the form with **`keepDirtyValues` semantics**: never clobber a field the user already touched.

```ts
function applyExtraction(result: ExtractionResult) {
  const dirty = form.formState.dirtyFields;
  const skipped: string[] = [];
  for (const [path, value] of extractionToFormEntries(result)) {
    if (get(dirty, path)) { skipped.push(path); continue; }
    form.setValue(path, value, { shouldDirty: true, shouldValidate: false });
    origin.markAi(path, { jobId, original: value });
    bumpRevision(path);
  }
  if (skipped.length) toast.info(`Kept your edits in ${skipped.length} field(s).`);
}
```

### 4.3 Distinguishing AI-filled fields

A `Map<FieldPath, FieldOrigin>` lives in a small Zustand store (`features/ai/origin-store.ts`) beside the form — deliberately *not* in RHF state.

- **AI, untouched**: violet left accent bar, `bg-violet-500/5`, `✨ AI` chip with inline `Revert`.
- **AI, then edited**: dimmed bar, chip reads `✨ AI · edited`.
- **User-typed**: no decoration.
- `AiReviewBar` (sticky): "3 of 6 AI fields reviewed · Next →".
- Per-field `Revert` (restores `origin.original`) + `Revert all AI fields` behind a confirm dialog.

### 4.4 Per-field Enhance / Generate — never overwrite

**Hard rule: an AI response is never written into an editor without an explicit user action.** The result lands in a *suggestion panel* below the editor.

```ts
// features/ai/use-field-suggestion.ts
export type SuggestionState =
  | { status: 'idle' }
  | { status: 'loading'; op: AiEnhanceOp; startedAt: number }
  | { status: 'ready'; op: AiEnhanceOp; suggestion: RichText; baseline: RichText; overLimit: boolean }
  | { status: 'error'; op: AiEnhanceOp; message: string; retryable: boolean };
```

Panel UI when `ready`:

```
┌ ✨ Suggested rewrite ────────────────────── [Side-by-side ▾] ┐
│  <rendered suggestion HTML, scrollable, max-h-64>            │
│  412 / 390 characters — over the limit ⚠  (only if overLimit)│
│  [Replace]  [Insert below]  [Copy]  [Try again]  [Discard]   │
└──────────────────────────────────────────────────────────────┘
```

- Loading state is **scoped**: only that block's button becomes a spinner + "Cancel"; the editor stays fully editable and every other AI button stays enabled.
- "Generate from long" is disabled with a tooltip when the long form is empty.
- If the user typed in the target editor while the request was in flight, the panel shows "You edited this while we were working" and hides `Replace` behind a confirm.
- If a suggestion exceeds the cap, `Replace` is disabled with `Shorten again` offered instead — never silently truncate.
- `Replace` = one Tiptap transaction ⇒ Cmd+Z restores the original. Plus a 6-second "Undo" toast.
- Requests carry an `Idempotency-Key` so a double-click can't spend two LLM calls.

---

## 5. Auth

**BFF / token-handler pattern. The browser never sees a JWT.**

- `POST /api/auth/login` (Next Route Handler) → FastAPI `/auth/login`; on success sets:
  - `aipm_at` — access token, `httpOnly; Secure; SameSite=Lax; Path=/; Max-Age=<exp>`
  - `aipm_rt` — refresh token, `httpOnly; Secure; SameSite=Strict; Path=/api/auth`
  - `aipm_csrf` — random, **readable** by JS; every mutating BFF request echoes it in `X-CSRF-Token` (double-submit)
- All data traffic goes through `app/api/bff/[...path]/route.ts`, which reads the cookie, sets `Authorization: Bearer`, and streams to `FASTAPI_URL`.
- **Refresh**: on 401 from FastAPI the proxy handler attempts one refresh (single-flight), retries the original request, and rotates cookies. On failure it clears cookies and returns `{ code: 'SESSION_EXPIRED' }`.
- **`proxy.ts`** (root, *not* `middleware.ts` — renamed in Next 16.0) does only a coarse cookie-presence check + redirect — real enforcement is `requireSession()` in `(app)/layout.tsx` and inside every BFF handler.

```ts
// proxy.ts
import { NextResponse, type NextRequest } from 'next/server';

const PUBLIC = ['/login', '/register', '/forgot-password'];

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const hasSession = req.cookies.has('aipm_at') || req.cookies.has('aipm_rt');
  const isPublic = PUBLIC.some((p) => pathname.startsWith(p));

  if (!hasSession && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  if (hasSession && isPublic) return NextResponse.redirect(new URL('/dashboard', req.url));
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|svg|woff2)$).*)'],
};
```

---

## 6. API client layer

Codegen via **`@hey-api/openapi-ts`** — do not hand-write these types.

```ts
// openapi-ts.config.ts
import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: process.env.OPENAPI_URL ?? 'http://localhost:8000/openapi.json',
  output: { path: './src/client', format: 'prettier', lint: 'eslint' },
  plugins: [
    '@hey-api/client-fetch',
    { name: '@hey-api/typescript', enums: 'javascript' },
    { name: '@hey-api/sdk', instance: true },
    '@tanstack/react-query',
    'zod',
  ],
});
```

`"gen:api": "openapi-ts"` in `package.json`; output committed and CI-checked. Runtime config once, in `lib/api-client.ts`:

```ts
client.setConfig({
  baseUrl: '/api/bff',
  credentials: 'same-origin',
  headers: { 'X-CSRF-Token': readCsrfCookie() },
});
```

---

## 7. Validation (Zod 4, mirrored client-side)

```ts
// features/projects/schema.ts
import { z } from 'zod';
import { countPlain } from '@/lib/rich-text/count';

const richText = (limit: number, label: string) =>
  z.object({ html: z.string(), text: z.string() })
    .refine((v) => countPlain(v.text) <= limit,
      { message: `${label} must be ${limit.toLocaleString()} characters or fewer`, path: ['text'] });

const nonEmptyRich = (limit: number, label: string, msg: string) =>
  richText(limit, label).refine((v) => v.text.trim().length > 0, { message: msg, path: ['text'] });

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Pick a date');

export const projectFormSchema = z.object({
  name: z.string().trim().min(1, 'Project name is required').max(200),
  role: z.string().trim().min(1, 'Your role is required').max(120),

  startDate: isoDate,
  endDate: isoDate.nullable(),
  isCurrent: z.boolean(),

  description: z.object({
    long:  richText(10_000, 'Long form'),
    short: nonEmptyRich(390, 'Short summary', 'Short summary is required'),
  }),
  responsibilities: z.object({
    long:  richText(10_000, 'Long form'),
    short: richText(390, 'Short summary'),
  }),

  technologies: z.array(z.string().trim().min(1).max(40))
    .max(40, 'At most 40 technologies')
    .refine((a) => new Set(a.map((s) => s.toLowerCase())).size === a.length, 'Duplicate technology'),

  projectUrl: z.union([z.literal(''), z.string().url()])
    .refine((v) => v === '' || /^https?:\/\//i.test(v), 'Must start with http:// or https://')
    .transform((v) => (v === '' ? null : v)),
})
.superRefine((v, ctx) => {
  if (v.isCurrent) {
    if (v.endDate) ctx.addIssue({ code: 'custom', path: ['endDate'],
      message: 'Clear the end date or uncheck Current Project' });
    return;
  }
  if (!v.endDate) return ctx.addIssue({ code: 'custom', path: ['endDate'], message: 'End date is required' });
  if (v.endDate < v.startDate) ctx.addIssue({ code: 'custom', path: ['endDate'],
    message: 'End date must be on or after the start date' });
})
.superRefine((v, ctx) => {
  if (v.startDate > todayIso()) ctx.addIssue({ code: 'custom', path: ['startDate'],
    message: 'Start date cannot be in the future' });
});

export type ProjectFormValues = z.input<typeof projectFormSchema>;
```

- **Dates as `yyyy-MM-dd` strings, not `Date`.** Lexicographic comparison is correct for ISO dates, zero timezone drift.
- **Current Project interaction**: checking it → `setValue('endDate', null, { shouldValidate: true })`, disables the End Date trigger, renders **"Present"**.
- **Caps enforced twice**: Tiptap's `limit` prevents exceeding by typing; Zod catches programmatic paths (AI accept, restored draft, pasted content).
- Mode: `zodResolver(projectFormSchema)`, `mode: 'onTouched'`. **Save Project** is `disabled={!isValid || isSubmitting}` with an explanatory line next to it.

---

## 8. Unsaved-work protection

1. **Tab close / reload** — `beforeunload` while `formState.isDirty`.
2. **Client-side navigation** — `<Link onNavigate>` (added 15.3) receives an event with `preventDefault()`. `NavigationBlockerProvider` in `(app)/layout.tsx` + a `GuardedLink` used by every nav link. Lint rule: `no-restricted-imports` on `next/link` outside `components/common/guarded-link.tsx`.
3. **Draft autosave to `localStorage`**:

```ts
// features/drafts/use-draft-autosave.ts
const key = (id: string) => `aipm:draft:v1:${id}`;

export function useDraftAutosave(id: string, form: UseFormReturn<ProjectFormValues>) {
  const values = useWatch({ control: form.control });
  const save = useDebouncedCallback((v) => {
    localStorage.setItem(key(id), JSON.stringify({ v, at: Date.now(), version: 1 }));
  }, 1200);

  useEffect(() => { if (form.formState.isDirty) save(values); }, [values]);
}
```

Restore is **opt-in, never automatic**: a banner offers "Restore" / "Discard". Drafts expire after 7 days; keys are namespaced per user id.

---

## 9. Milestones — each one runs in a browser

| # | Deliverable | Runnable proof |
|---|---|---|
| **M0** | `create-next-app` (Next 16, TS, Turbopack) + Tailwind 4.3 + shadcn (Base UI) + dark tokens + `AppShell` + `/styleguide` | Dark shell renders; primitives styled to the mockup |
| **M1** | Auth vertical slice: `/login`, `/register`, BFF `/api/auth/*` against a mocked FastAPI, `proxy.ts`, `requireSession()`, empty `/dashboard` + `/projects` | Log in → land on dashboard; hit `/projects` logged out → bounced to `/login?next=` |
| **M2** | Codegen wired, dashboard lists real project cards, card → `/projects/[id]` detail | Real data renders; card click navigates |
| **M3** | `RichTextEditor` standalone with toolbar + `CharacterCount` cap + counter | Type past 390 → blocked at `390/390`; typing causes no parent re-render |
| **M4** | `ProjectForm` end to end, AI-free: all 8 field groups, `DualEditorField` used twice, Current Project ↔ End Date, chips, footer | Fill by hand, save, see it on dashboard, reopen in edit mode |
| **M5** | Unsaved-work protection: guarded navigation, `beforeunload`, draft autosave + restore banner | Type, click sidebar → dialog; reload → restore banner |
| **M6** | Upload → job polling: dropzone, `useExtractionJob`, stage stepper, error taxonomy, resume-after-refresh | Upload a PDF, watch stages, form fills, refresh mid-job resumes |
| **M7** | AI provenance + review: origin store, accent bars, chips, per-field Revert, `AiReviewBar` | AI fields visually distinct; revert restores extracted value |
| **M8** | Per-field AI: `useFieldSuggestion`, scoped spinners, `AiSuggestionPanel`, over-limit and baseline-changed guards, undo | Enhance on hand-written prose → suggestion panel, prose untouched until Replace |
| **M9** | `/settings/ai-providers`: Ollama + Gemini, masked key inputs, Test connection | Save a provider, Test connection reports OK/failure |
| **M10** | Export: PDF / DOCX via the BFF | Download a real PDF and DOCX |
| **M11** | Hardening: skeletons, error boundaries, empty states, a11y audit, Playwright E2E, Lighthouse | Full happy path + failure paths green in CI |

M0–M2 sequential. M3 independent, parallel with M1/M2. M6–M8 strictly ordered; M4 precedes M6.

## Risk register (ranked)

1. **Destructive overwrite of hand-written prose** — mitigated by never-write-without-accept, single-transaction replacement (Cmd+Z), baseline-changed detection, undo toast.
2. **Editor re-mount wiping undo history** — guard with `memo` + the `revision` protocol.
3. **Tiptap paste-over-limit blanking the editor** (upstream #4820) — explicit `handlePaste` truncation.
4. **`html`/`text` desync in `RichText`** — backend recomputes and rejects mismatches.
5. **Following a pre-16 tutorial and creating `middleware.ts`** — deprecated; CI-grep for it.
6. **shadcn Calendar vs `@daypicker/react` v10 prop drift** — wrap in our own `DateField`.
7. **Timezone drift on dates** — eliminated structurally by never putting a `Date` object in form state.

Sources: [Next.js 16.3 blog](https://nextjs.org/blog/next-16-3-ai-improvements) · [proxy.js reference](https://nextjs.org/docs/app/api-reference/file-conventions/proxy) · [Link onNavigate](https://nextjs.org/docs/app/api-reference/components/link) · [shadcn/ui: Base UI as the Default](https://ui.shadcn.com/docs/changelog/2026-07-base-ui-default) · [Tiptap CharacterCount](https://tiptap.dev/docs/editor/extensions/functionality/character-count) · [Tiptap performance / useEditorState](https://tiptap.dev/docs/guides/performance) · [TanStack Query polling guide](https://tanstack.com/query/v5/docs/framework/react/guides/polling) · [FastAPI: Generating SDKs](https://fastapi.tiangolo.com/advanced/generate-clients/) · [Hey API TanStack Query plugin](https://heyapi.dev/docs/openapi/typescript/plugins/tanstack-query) · [React DayPicker v10 upgrading](https://daypicker.dev/upgrading)
