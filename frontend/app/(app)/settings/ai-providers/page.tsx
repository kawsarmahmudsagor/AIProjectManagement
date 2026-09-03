import { AgentPersonaSelect } from "@/components/settings/agent-persona-select";
import { DefaultProviderSelect } from "@/components/settings/default-provider-select";
import { ProviderCard } from "@/components/settings/provider-card";
import { serverApiFetch } from "@/lib/server-api";
import type { AgentPersona, ProviderModelCatalogResponse, ProviderSetting, UserOut } from "@/lib/types";

const FALLBACK_MODELS: ProviderModelCatalogResponse = {
  gemini: { models: ["gemini-3.5-flash"], default: "gemini-3.5-flash" },
  openai: { models: ["gpt-4.1-mini"], default: "gpt-4.1-mini" },
};

export default async function AiProvidersPage() {
  let settings: ProviderSetting[] = [];
  let modelCatalog: ProviderModelCatalogResponse = FALLBACK_MODELS;
  let agentPersona: AgentPersona = "business_analyst";
  try {
    settings = await serverApiFetch<ProviderSetting[]>("ai-settings");
  } catch {
    // backend not reachable yet — cards still render with empty defaults
  }
  try {
    modelCatalog = await serverApiFetch<ProviderModelCatalogResponse>("ai-settings/models");
  } catch {
    // backend not reachable yet — fall back to the hardcoded defaults above
  }
  try {
    agentPersona = (await serverApiFetch<UserOut>("auth/me")).agent_persona;
  } catch {
    // backend not reachable yet — dropdown still renders, defaulted to Business Analyst
  }

  return (
    <div className="grid max-w-2xl gap-6">
      <AgentPersonaSelect initial={agentPersona} />
      <DefaultProviderSelect initial={settings} />
      <ProviderCard
        provider="gemini"
        title="Google Gemini"
        description="Requires an API key with billing enabled — the free tier trains on your data, and project documents can contain personal information. Standard (unrestricted) keys are being phased out; create a fresh key at aistudio.google.com/api-keys if Test connection fails with an auth error."
        initial={settings.find((s) => s.provider === "gemini")}
        modelCatalog={modelCatalog.gemini}
      />
      <ProviderCard
        provider="openai"
        title="OpenAI"
        description="Requires an API key with billing enabled at platform.openai.com. Handles scanned PDFs and multi-column layouts well via document vision."
        initial={settings.find((s) => s.provider === "openai")}
        modelCatalog={modelCatalog.openai}
      />
    </div>
  );
}
