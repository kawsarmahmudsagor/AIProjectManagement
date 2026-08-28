import { DefaultProviderSelect } from "@/components/settings/default-provider-select";
import { ProviderCard } from "@/components/settings/provider-card";
import { serverApiFetch } from "@/lib/server-api";
import type { ProviderModelCatalogResponse, ProviderSetting } from "@/lib/types";

const FALLBACK_MODELS: ProviderModelCatalogResponse = {
  gemini: { models: ["gemini-3.5-flash"], default: "gemini-3.5-flash" },
  ollama: { models: ["gemma4:e2b", "gemma4:e4b"], default: "gemma4:e2b" },
};

export default async function AiProvidersPage() {
  let settings: ProviderSetting[] = [];
  let modelCatalog: ProviderModelCatalogResponse = FALLBACK_MODELS;
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

  return (
    <div className="grid max-w-2xl gap-6">
      <DefaultProviderSelect initial={settings} />
      <ProviderCard
        provider="gemini"
        title="Google Gemini"
        description="Requires an API key with billing enabled — the free tier trains on your data, and project documents can contain personal information. Standard (unrestricted) keys are being phased out; create a fresh key at aistudio.google.com/api-keys if Test connection fails with an auth error."
        initial={settings.find((s) => s.provider === "gemini")}
        modelCatalog={modelCatalog.gemini}
      />
      <ProviderCard
        provider="ollama"
        title="Ollama (local)"
        description="Runs on your machine — private, but weaker on scanned PDFs, multi-column layouts, and very long documents than Gemini."
        initial={settings.find((s) => s.provider === "ollama")}
        modelCatalog={modelCatalog.ollama}
      />
    </div>
  );
}
