// Mirrors backend/app/schemas/*.py. Will be replaced by @hey-api/openapi-ts codegen
// once the schema stabilizes (DESIGN.md §6) — hand-kept in sync until then.

export type RichText = { html: string; text: string };

export type ProjectSummary = {
  id: string;
  name: string;
  role: string;
  start_date: string;
  end_date: string | null;
  is_current: boolean;
  short_summary_text: string;
};

export type ProjectListResponse = { items: ProjectSummary[]; total: number };

export type ProjectSection = { long: RichText; short: RichText };

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
};

export type ProviderSetting = {
  id: string;
  provider: "gemini" | "ollama";
  api_key_masked: string | null;
  base_url: string | null;
  default_model: string | null;
  is_default: boolean;
};

export type ProviderModelCatalog = { models: string[]; default: string };

export type ProviderModelCatalogResponse = Record<"gemini" | "ollama", ProviderModelCatalog>;

export type AgentPersona = "business_analyst" | "technical_developer";

export type UserOut = { id: string; email: string; agent_persona: AgentPersona };

export type UploadResponse = { document_id: string; job_id: string };

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
