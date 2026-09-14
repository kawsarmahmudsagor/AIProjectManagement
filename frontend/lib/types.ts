// Mirrors backend/app/schemas/*.py. Will be replaced by @hey-api/openapi-ts codegen
// once the schema stabilizes (DESIGN.md §6) — hand-kept in sync until then.

export type RichText = { html: string; text: string };

export type ProjectMediaRef = {
  url: string;
  mime_type: string;
  size_bytes: number;
  origin: "uploaded" | "generated";
  generator: string | null;
};

export type ProjectSummary = {
  id: string;
  name: string;
  role: string;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  short_summary_text: string;
  technologies: string[];
  thumbnail_url: string | null;
  video_url: string | null;
};

export type ProjectListResponse = { items: ProjectSummary[]; total: number };

export type ProjectSection = { long: RichText; short: RichText };

export type FaqItem = { question: string; answer: string };

export type Project = {
  id: string;
  name: string;
  role: string;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  description: ProjectSection;
  responsibilities: ProjectSection;
  technologies: string[];
  project_url: string | null;
  created_at: string;
  updated_at: string;
  thumbnail: ProjectMediaRef | null;
  video: ProjectMediaRef | null;
  // Auto-generated once at project creation (backend/app/services/faq_service.py) —
  // always a list, never absent; empty means "nothing generated (yet)", not an error.
  faq: FaqItem[];
  // Stills extracted from `video` for the read-only detail-page carousel — empty when
  // there's no video, or extraction hasn't finished yet.
  video_frames: ProjectMediaRef[];
};

export type ThumbnailGenerationContext = {
  name?: string;
  role?: string;
  technologies?: string[];
  description_text?: string;
  responsibilities_text?: string;
};

export type ThumbnailJobStatus = {
  id: string;
  status: JobStatus;
  result: ProjectMediaRef | null;
  error: ErrorDetail | null;
};

export type DashboardTechnology = { name: string; project_count: number };

export type DashboardSummary = {
  total_projects: number;
  current_projects: number;
  technologies: DashboardTechnology[];
  distinct_technology_count: number;
  primary_skills: string[];
  secondary_skills: string[];
  projects: ProjectSummary[];
};

export type SearchHitKind = "project" | "technology" | "task" | "app_feature";

export type SearchHit = {
  kind: SearchHitKind;
  id: string;
  title: string;
  subtitle: string;
  snippet: string;
  href: string;
  score: number;
  meta: Record<string, unknown>;
};

export type SearchGroup = { kind: SearchHitKind; label: string; items: SearchHit[]; total: number };

export type SearchResponse = { q: string; groups: SearchGroup[]; total: number };

export type SearchAnswer = { answer: string; citations: SearchHit[] };

export type ChatAttachmentKind = "image" | "document";

export type ChatAttachment = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  kind: ChatAttachmentKind;
  url: string;
  extracted_chars: number | null;
  text_truncated: boolean;
};

export type ProviderSetting = {
  id: string;
  provider: "gemini" | "openai";
  api_key_masked: string | null;
  base_url: string | null;
  default_model: string | null;
  is_default: boolean;
};

export type ProviderModelCatalog = { models: string[]; default: string };

export type ProviderModelCatalogResponse = Record<"gemini" | "openai", ProviderModelCatalog>;

export type AgentPersona = "business_analyst" | "technical_developer";
export type ChatProvider = "gemini" | "openai";

export type UserOut = {
  id: string;
  email: string;
  agent_persona: AgentPersona;
  first_name: string;
  middle_name: string | null;
  last_name: string | null;
  preferred_name: string | null;
  chat_provider: ChatProvider;
  chatbot_preemptive_github_suggestions: boolean;
};

// job_id is null when purpose="store_only" (the AI work-breakdown upload path) — no
// ExtractionJob is created in that case, so there's nothing to poll.
export type UploadResponse = { document_id: string; job_id: string | null };

export type JobStatus =
  | "queued"
  | "parsing"
  | "extracting"
  | "structuring"
  | "succeeded"
  | "failed"
  | "cancelled";

// Every field is null/empty when the document didn't state it — providers are
// instructed to never infer or invent a value (backend/app/providers/prompts.py), so a
// missing field here must stay empty for the human to fill in, not be guessed at.
export type ExtractedProject = {
  name: string | null;
  role: string | null;
  start_date: string | null;
  end_date: string | null;
  description: ProjectSection;
  responsibilities: ProjectSection;
  technologies: string[];
};

export type ExtractionResult = { project: ExtractedProject; confidence_notes: string[] };

export type ErrorDetail = { code: string; message: string; provider?: string | null };

export type ExtractionJobStatus = {
  id: string;
  status: JobStatus;
  result: ExtractionResult | null;
  error: ErrorDetail | null;
};

// Mirrors backend/app/schemas/task.py and backend/app/models/task.py.
export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";
export type TaskSource = "manual" | "ai";

export type Task = {
  id: string;
  project_id: string;
  parent_id: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  source: TaskSource;
  estimate_minutes: number | null;
  due_date: string | null;
  position: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  subtask_total: number;
  subtask_done: number;
};

// The list-row projection — no `description`, matching ProjectSummary's convention.
export type TaskSummary = Omit<Task, "description" | "created_at" | "updated_at">;

export type TaskListResponse = { items: TaskSummary[]; total: number };

export type TaskCreatePayload = {
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  estimate_minutes?: number | null;
  due_date?: string | null;
  parent_id?: string | null;
};

export type TaskUpdatePayload = Partial<TaskCreatePayload>;

export type TaskListFilters = {
  q?: string;
  status?: TaskStatus[];
  priority?: TaskPriority[];
  include_subtasks?: boolean;
  sort?: "board" | "position" | "due_date" | "priority" | "created_at" | "updated_at";
  order?: "asc" | "desc";
};

// Mirrors backend/app/schemas/breakdown.py — the AI work-breakdown flagship feature.
export type EstimateSize = "xs" | "s" | "m" | "l" | "xl";

export type ProposedTask = {
  ref: string;
  title: string;
  description: string;
  grounded: boolean;
  phase: string | null;
  parent_ref: string | null;
  priority: TaskPriority;
  estimate_size: EstimateSize | null;
  source_quote: string | null;
};

export type BreakdownResult = { tasks: ProposedTask[]; confidence_notes: string[] };

export type BreakdownJob = {
  id: string;
  status: JobStatus;
  document_id: string | null;
  prompt: string | null;
  max_tasks: number;
  is_scanned: boolean;
  result: BreakdownResult | null;
  // ref -> id of the Task actually created for it (empty until something is accepted).
  accepted: Record<string, string>;
  dismissed_refs: string[];
  error_code: string | null;
  error_message: string | null;
};

export type BreakdownCreatePayload = {
  document_id?: string | null;
  prompt?: string | null;
  provider?: "gemini" | "openai";
  max_tasks?: number;
};

export type BreakdownAcceptItem = {
  ref: string;
  title: string;
  description?: string;
  priority?: TaskPriority;
  estimate_minutes?: number | null;
  estimate_size?: EstimateSize | null;
  phase?: string | null;
  parent_ref?: string | null;
};

export type BreakdownSkippedItem = { ref: string; reason: string };

export type BreakdownAcceptResponse = {
  created: Task[];
  skipped: BreakdownSkippedItem[];
  promoted_refs: string[];
};

// Mirrors backend/app/schemas/brag_document.py — the Brag Document Generator feature.
export type BragDocumentPreviewResponse = {
  document_id: string;
  detected_member_name: string | null;
  match_confidence: number;
  candidate_member_names: string[];
  // e.g. "August 2026" — display as-is, pass back to POST /brag-documents as-is.
  available_months: string[];
};

export type BragDocumentCreatePayload = {
  document_id: string;
  member_name: string;
  target_month: string;
  provider?: ChatProvider | null;
  // Omit to default to "{target_month} Brag Document" (backend/app/models/brag_document_job.py).
  name?: string | null;
};

// One row in the saved-documents list shown on the Brag Documents page.
export type BragDocumentJobSummary = {
  id: string;
  name: string;
  status: JobStatus;
  member_name: string;
  target_month: string;
  created_at: string;
};

export type BragDocumentJobListResponse = {
  items: BragDocumentJobSummary[];
  total: number;
};

export type BragDocumentBulletGroup = { heading: string; bullets: string[] };

// `subsections` and `bullets` are alternatives, not both-populated — a group with
// distinct sub-themes uses subsections, a simpler one uses the flat bullets list.
export type BragDocumentTechnicalContributionGroup = {
  project_name: string;
  bullets: string[];
  subsections: BragDocumentBulletGroup[];
  key_contribution: string;
};

export type BragDocumentImpactArea = { category: string; summary: string };

// LLM-facing result — no hour fields anywhere (those live only in HourStats, a separate
// deterministic column so the LLM's output can never overwrite the arithmetic).
export type BragDocumentResult = {
  technical_contributions: BragDocumentTechnicalContributionGroup[];
  team_support_bullets: string[];
  learning_bullets: string[];
  overall_impact: BragDocumentImpactArea[];
  confidence_notes: string[];
};

// Mirrors MemberMonthlySummary 1:1 — every field here is deterministic Python arithmetic,
// never LLM-authored.
export type HourStats = {
  member_name: string;
  month_name: string;
  year: number;
  included_weeks: string[];
  total_hours: number;
  expected_target_hours: number;
  gross_base_hours: number;
  holiday_deducted_hours: number;
  holiday_count: number;
  holiday_names: string[];
  leave_count: number;
  leave_hours: number;
  leave_dates: string[];
  blocker_count: number;
  billable_hours: number;
  non_billable_hours: number;
  balance_hours: number;
  target_completion_pct: number;
};

export type BragDocumentJob = {
  id: string;
  name: string;
  status: JobStatus;
  document_id: string;
  member_name: string;
  target_month: string;
  // Always the effective content (the user's saved edit once one exists, else the
  // original LLM draft) — `is_edited` says which, so the UI can offer "Reset changes".
  result: BragDocumentResult | null;
  is_edited: boolean;
  hour_stats: HourStats | null;
  error_code: string | null;
  error_message: string | null;
};
