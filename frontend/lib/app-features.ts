/** Client-side mirror of backend/app/search/app_features.py — kept in sync by hand (same
 * discipline as that file's own docstring: update both in the same PR as any feature
 * change). This is what lets the dashboard search bar show "Pages & features" results
 * instantly, with no round-trip, while the project/task/technology groups still come
 * from GET /search. */

export type AppFeature = {
  slug: string;
  title: string;
  path: string;
  description: string;
  keywords: readonly string[];
};

export const APP_FEATURES: AppFeature[] = [
  {
    slug: "add-project",
    title: "Add a project",
    path: "/projects/new",
    description: "Create a project by hand, or upload a PDF/DOCX/TXT and let AI extract it.",
    keywords: ["new project", "create project", "add project", "import", "upload document", "extract", "pdf", "docx"],
  },
  {
    slug: "ai-extraction",
    title: "AI extraction from a document",
    path: "/projects/new",
    description: "Upload a project document and let AI fill in a structured project entry.",
    keywords: ["extraction", "ai extract", "parse document", "scanned pdf", "autofill"],
  },
  {
    slug: "enhance-with-ai",
    title: "Enhance with AI",
    path: "/projects",
    description: "Rewrite a long description, or generate the short summary from it.",
    keywords: ["enhance", "rewrite", "generate short", "improve wording", "ai suggestion"],
  },
  {
    slug: "agent-persona",
    title: "Agent Persona",
    path: "/settings/ai-providers",
    description: "Choose the voice AI uses for extraction, rewrites, and breakdowns.",
    keywords: ["persona", "tone", "voice", "business analyst", "technical developer"],
  },
  {
    slug: "ai-providers",
    title: "AI Provider settings",
    path: "/settings/ai-providers",
    description: "Add a Gemini or OpenAI API key, pick a model, and set the default provider.",
    keywords: ["api key", "gemini", "openai", "model", "provider", "settings", "token", "test connection"],
  },
  {
    slug: "tasks",
    title: "Tasks",
    path: "/projects",
    description: "Every project has its own task list: status, priority, due date, and estimate.",
    keywords: ["task", "todo", "kanban", "due date", "subtask", "priority", "status"],
  },
  {
    slug: "ai-breakdown",
    title: "AI work breakdown",
    path: "/projects",
    description: "Upload a spec or describe the work, and AI proposes a list of tasks to review.",
    keywords: ["breakdown", "break down", "split work", "plan feature", "estimate", "propose tasks"],
  },
  {
    slug: "export",
    title: "Export a project",
    path: "/projects",
    description: "Export a saved project as a PDF or DOCX file from its detail page.",
    keywords: ["export", "pdf", "docx", "download", "word document"],
  },
  {
    slug: "jarvis",
    title: "Jarvis (the chatbot)",
    path: "/conversations",
    description: "Ask Jarvis about your own projects, work history, or open-source tools.",
    keywords: ["chat", "chatbot", "jarvis", "ask", "assistant", "attach", "attachment"],
  },
  {
    slug: "conversations",
    title: "Conversations",
    path: "/conversations",
    description: "Search, star, sort, resume, or delete past conversations with Jarvis.",
    keywords: ["conversations", "chat history", "starred", "resume chat"],
  },
  {
    slug: "suggestions",
    title: "Suggested for you",
    path: "/dashboard",
    description: "Real GitHub repos suggested based on the technologies across your projects.",
    keywords: ["suggestions", "github", "open source", "repos", "recommended"],
  },
  {
    slug: "brag-document",
    title: "Brag Document Generator",
    path: "/brag-documents",
    description: "Upload the team standup workbook and generate a monthly performance report.",
    keywords: [
      "brag document",
      "standup",
      "spreadsheet",
      "xlsx",
      "excel",
      "monthly report",
      "achievements",
      "self review",
      "performance report",
    ],
  },
  {
    slug: "profile",
    title: "Profile",
    path: "/profile",
    description: "Optional photo, bio, designation, and skills — used as soft context by Jarvis.",
    keywords: ["profile", "photo", "skills", "bio", "designation", "team", "organization"],
  },
];

/** Same AND-over-tokens matching rule as the backend's _search_app_features, so results
 * are consistent whether a query happens to be answered client-side or server-side. */
export function searchAppFeatures(q: string): AppFeature[] {
  const tokens = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return [];

  return APP_FEATURES.filter((feature) =>
    tokens.every(
      (token) =>
        feature.title.toLowerCase().includes(token) ||
        feature.description.toLowerCase().includes(token) ||
        feature.keywords.some((kw) => kw.toLowerCase().includes(token)),
    ),
  );
}
