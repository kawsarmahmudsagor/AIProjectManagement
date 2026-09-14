"""Static registry of the app's own pages and features, so the global search bar can
answer "where do I do X" — the "anything regarding the app, or a feature" half of the
requirement — with no DB and no LLM.

Seeded BY HAND from app/agents/chat_app_guide.md's `##` sections, and deliberately not
parsed from it at runtime: that guide is prose written for an LLM, its headings aren't
routes, and it carries no path/keyword data — a markdown parser would silently emit
garbage rows the first time someone reflowed a paragraph. The coupling is instead enforced
at test time (tests/test_app_features_registry.py) by asserting every `##` heading in
that file is cited by at least one entry's `guide_section` below, so adding a feature
section to the guide without registering it here fails loudly in CI rather than quietly
making it unsearchable. Keep this in the same PR as any user-facing feature change,
exactly like chat_app_guide.md itself (see that file's own header comment).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppFeature:
    slug: str
    title: str
    path: str  # frontend route
    description: str  # one sentence, shown as the result snippet
    keywords: tuple[str, ...]  # synonyms a user would actually type
    guide_section: str  # the exact `##` heading in chat_app_guide.md this mirrors


APP_FEATURES: list[AppFeature] = [
    AppFeature(
        "add-project",
        "Add a project",
        "/projects/new",
        "Create a project by hand, or upload a PDF/DOCX/TXT and let AI extract it.",
        ("new project", "create project", "add project", "import", "upload document", "extract", "pdf", "docx"),
        "Adding a project",
    ),
    AppFeature(
        "ai-extraction",
        "AI extraction from a document",
        "/projects/new",
        "Upload a project document and let AI fill in a structured project entry.",
        ("extraction", "ai extract", "parse document", "scanned pdf", "autofill"),
        "AI extraction from an uploaded document",
    ),
    AppFeature(
        "enhance-with-ai",
        "Enhance with AI",
        "/projects",
        "Rewrite a long description, or generate the short summary from it.",
        ("enhance", "rewrite", "generate short", "improve wording", "ai suggestion"),
        "Enhance with AI / Generate from long",
    ),
    AppFeature(
        "agent-persona",
        "Agent Persona",
        "/settings/ai-providers",
        "Choose the voice AI uses for extraction, rewrites, and breakdowns.",
        ("persona", "tone", "voice", "business analyst", "technical developer"),
        "Agent Persona (Settings > AI Providers)",
    ),
    AppFeature(
        "ai-providers",
        "AI Provider settings",
        "/settings/ai-providers",
        "Add a Gemini or OpenAI API key, pick a model, and set the default provider.",
        ("api key", "gemini", "openai", "model", "provider", "settings", "token", "test connection"),
        "AI Provider settings (Settings > AI Providers)",
    ),
    AppFeature(
        "tasks",
        "Tasks",
        "/projects",
        "Every project has its own task list: status, priority, due date, and estimate.",
        ("task", "todo", "kanban", "due date", "subtask", "priority", "status"),
        "Tasks",
    ),
    AppFeature(
        "ai-breakdown",
        "AI work breakdown",
        "/projects",
        "Upload a spec or describe the work, and AI proposes a list of tasks to review.",
        ("breakdown", "break down", "split work", "plan feature", "estimate", "propose tasks"),
        "AI work breakdown",
    ),
    AppFeature(
        "export",
        "Export a project",
        "/projects",
        "Export a saved project as a PDF or DOCX file from its detail page.",
        ("export", "pdf", "docx", "download", "word document"),
        "Export",
    ),
    AppFeature(
        "jarvis",
        "Jarvis (the chatbot)",
        "/conversations",
        "Ask Jarvis about your own projects, work history, or open-source tools.",
        ("chat", "chatbot", "jarvis", "ask", "assistant", "attach", "attachment"),
        "Jarvis (the chatbot)",
    ),
    AppFeature(
        "conversations",
        "Conversations",
        "/conversations",
        "Search, star, sort, resume, or delete past conversations with Jarvis.",
        ("conversations", "chat history", "starred", "resume chat"),
        "Conversations page",
    ),
    AppFeature(
        "suggestions",
        "Suggested for you",
        "/dashboard",
        "Real GitHub repos suggested based on the technologies across your projects.",
        ("suggestions", "github", "open source", "repos", "recommended"),
        "Dashboard — Suggested for you",
    ),
    AppFeature(
        "brag-document",
        "Brag Document Generator",
        "/brag-documents",
        "Upload the team standup workbook and generate a monthly performance report.",
        (
            "brag document",
            "standup",
            "spreadsheet",
            "xlsx",
            "excel",
            "monthly report",
            "achievements",
            "self review",
            "performance report",
        ),
        "Brag Document Generator",
    ),
    AppFeature(
        "profile",
        "Profile",
        "/profile",
        "Optional photo, bio, designation, and skills — used as soft context by Jarvis.",
        ("profile", "photo", "skills", "bio", "designation", "team", "organization"),
        "Profile page",
    ),
]


__all__ = ["AppFeature", "APP_FEATURES"]
