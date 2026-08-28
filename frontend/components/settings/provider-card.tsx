"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { ProviderModelCatalog, ProviderSetting } from "@/lib/types";

type Props = {
  provider: "gemini" | "ollama";
  title: string;
  description: string;
  initial?: ProviderSetting;
  modelCatalog: ProviderModelCatalog;
};

export function ProviderCard({ provider, title, description, initial, modelCatalog }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? (provider === "ollama" ? "http://localhost:11434" : ""));
  const [defaultModel, setDefaultModel] = useState(initial?.default_model ?? modelCatalog.default);
  // Keep a previously-saved model in the list even if the curated catalog has since
  // moved on, so switching tabs never silently swaps out what's actually saved.
  const modelOptions =
    initial?.default_model && !modelCatalog.models.includes(initial.default_model)
      ? [initial.default_model, ...modelCatalog.models]
      : modelCatalog.models;
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await apiFetch(`ai-settings/${provider}`, {
        method: "PUT",
        body: JSON.stringify({
          api_key: apiKey || undefined,
          base_url: baseUrl || undefined,
          default_model: defaultModel || undefined,
        }),
      });
      setApiKey("");
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await apiFetch<{ ok: boolean; detail: string }>(`ai-settings/${provider}/test`, {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey || undefined, base_url: baseUrl || undefined, default_model: defaultModel || undefined }),
      });
      setTestResult(result);
    } catch (err) {
      setTestResult({ ok: false, detail: err instanceof ApiError ? err.message : "Test failed" });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-medium">{title}</h2>
        <p className="text-sm text-muted">{description}</p>
      </div>

      {provider === "gemini" && (
        <div>
          <label className="mb-1 block text-sm font-medium">API Key</label>
          <Input
            type="password"
            placeholder={initial?.api_key_masked ?? "Paste your Gemini API key"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
      )}

      {provider === "ollama" && (
        <>
          <div>
            <label className="mb-1 block text-sm font-medium">Base URL</label>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">API Key (optional)</label>
            <Input
              type="password"
              placeholder={initial?.api_key_masked ?? "Only needed for Ollama Cloud chat"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </>
      )}

      <div>
        <label className="mb-1 block text-sm font-medium">Models</label>
        <select
          value={defaultModel}
          onChange={(e) => setDefaultModel(e.target.value)}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none"
        >
          {modelOptions.map((model) => (
            <option key={model} value={model}>
              {model}
              {model === modelCatalog.default ? " (default)" : ""}
            </option>
          ))}
        </select>
      </div>

      {testResult && (
        <p className={`text-sm ${testResult.ok ? "text-success" : "text-danger"}`}>{testResult.detail}</p>
      )}
      {saveError && <p className="text-sm text-danger">{saveError}</p>}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={test} disabled={testing}>
          {testing ? "Testing…" : "Test connection"}
        </Button>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </Card>
  );
}
