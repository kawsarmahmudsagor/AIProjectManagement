"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, Search, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useShowProviderErrorModal } from "@/components/layout/provider-error-modal";
import { useChatWidget } from "@/components/chat/chat-widget-context";
import { AiOriginBadge } from "@/components/ui/ai-origin-badge";
import { Input } from "@/components/ui/input";
import { useAppliedPulse } from "@/hooks/use-applied-pulse";
import { useDebouncedCallback } from "@/hooks/use-debounced-callback";
import { useEnterTransition } from "@/hooks/use-enter-transition";
import { searchAppFeatures } from "@/lib/app-features";
import { ApiError } from "@/lib/api-client";
import { askApp, hrefForHit, searchApp } from "@/lib/search";
import type { SearchAnswer, SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

const MIN_QUERY_LENGTH = 2;

function featureHitsFromClientRegistry(q: string): SearchHit[] {
  return searchAppFeatures(q).map((f) => ({
    kind: "app_feature",
    id: f.slug,
    title: f.title,
    subtitle: "",
    snippet: f.description,
    href: f.path,
    score: 0,
    meta: {},
  }));
}

export function AppSearch() {
  const router = useRouter();
  const { openWithPrompt } = useChatWidget();
  const showProviderError = useShowProviderErrorModal();
  const [rawQuery, setRawQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [askAnswer, setAskAnswer] = useState<SearchAnswer | null>(null);
  const [askError, setAskError] = useState<string | null>(null);
  const [askApplied, pulseAskApplied] = useAppliedPulse();
  const visible = useEnterTransition(open);

  const { run: debounce } = useDebouncedCallback((q: string) => setDebouncedQuery(q), 250);

  const enabled = debouncedQuery.trim().length >= MIN_QUERY_LENGTH;
  const query = useQuery({
    queryKey: ["search", debouncedQuery],
    queryFn: ({ signal }) => searchApp(debouncedQuery, signal),
    enabled,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });

  const askMutation = useMutation({
    mutationFn: (q: string) => askApp(q),
    onSuccess: (answer) => {
      setAskAnswer(answer);
      setAskError(null);
      pulseAskApplied();
    },
    onError: (err) => {
      if (err instanceof ApiError && showProviderError({ code: err.code, provider: err.provider })) return;
      setAskError(err instanceof Error ? err.message : "Something went wrong");
    },
  });

  const featureHits = useMemo(() => (enabled ? featureHitsFromClientRegistry(debouncedQuery) : []), [enabled, debouncedQuery]);

  const groups = useMemo(() => {
    const serverGroups = (query.data?.groups ?? []).filter((g) => g.kind !== "app_feature");
    const combined = [...serverGroups];
    if (featureHits.length > 0) {
      combined.push({ kind: "app_feature", label: "Pages & features", items: featureHits, total: featureHits.length });
    }
    return combined;
  }, [query.data, featureHits]);

  const flatHits = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  const runAsk = () => {
    const q = rawQuery.trim();
    if (!q || askMutation.isPending) return;
    setAskAnswer(null);
    setAskError(null);
    askMutation.mutate(q);
  };

  const navigateTo = (hit: SearchHit) => {
    setOpen(false);
    setRawQuery("");
    setDebouncedQuery("");
    router.push(hrefForHit(hit));
  };

  return (
    <div
      className="relative"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false);
      }}
    >
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
        <Input
          value={rawQuery}
          onChange={(e) => {
            setRawQuery(e.target.value);
            debounce(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
            if (e.key === "Enter" && !enabled) runAsk();
          }}
          placeholder="Search projects, tasks, skills, or anything about the app…"
          className="pl-9"
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
        />
      </div>

      {open && (rawQuery.trim().length > 0 || askAnswer) && (
        <div
          role="listbox"
          className={cn(
            "absolute left-0 right-0 top-full z-40 mt-2 max-h-[420px] overflow-y-auto rounded-xl border border-border bg-surface shadow-elevation-3 transition duration-150 ease-out motion-reduce:transition-none",
            visible ? "scale-100 opacity-100" : "pointer-events-none scale-95 opacity-0",
          )}
        >
          {rawQuery.trim().length > 0 && (
            <div className={cn("border-b border-border p-2", askApplied && "ai-glow ai-glow--applied", askMutation.isPending && "ai-glow ai-glow--generating")}>
              {!askAnswer && !askMutation.isPending && (
                <button
                  type="button"
                  onClick={runAsk}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-accent hover:bg-accent/5"
                >
                  <Sparkles size={14} className="shrink-0" />
                  Ask Jarvis: &ldquo;{rawQuery.trim()}&rdquo;
                </button>
              )}
              {askMutation.isPending && (
                <div className="flex items-center gap-2 px-2 py-2 text-sm text-muted">
                  <Sparkles size={14} className="animate-pulse text-accent" /> Thinking…
                </div>
              )}
              {askError && (
                <div className="flex items-center gap-2 px-2 py-2 text-sm text-danger">
                  <AlertCircle size={14} className="shrink-0" /> {askError}
                </div>
              )}
              {askAnswer && (
                <div className="space-y-2 rounded-lg border border-accent/30 bg-accent/5 p-3">
                  <AiOriginBadge title="Answered by Jarvis" />
                  <p className="text-sm text-foreground/90">{askAnswer.answer}</p>
                  <button
                    type="button"
                    onClick={() => openWithPrompt(rawQuery.trim())}
                    className="flex items-center gap-1 text-xs text-accent hover:underline"
                  >
                    Continue in chat <ArrowRight size={12} />
                  </button>
                </div>
              )}
            </div>
          )}

          {enabled && query.isLoading && <p className="p-4 text-sm text-muted">Searching…</p>}

          {enabled && !query.isLoading && flatHits.length === 0 && (
            <p className="p-4 text-sm text-muted">No results for &ldquo;{debouncedQuery}&rdquo;.</p>
          )}

          {groups.map((group) =>
            group.items.length > 0 ? (
              <div key={group.kind} className="border-b border-border py-1 last:border-b-0">
                <p className="px-3 py-1 text-2xs font-semibold uppercase tracking-wide text-muted">{group.label}</p>
                {group.items.map((hit) => (
                  <button
                    key={`${hit.kind}-${hit.id}`}
                    role="option"
                    aria-selected={false}
                    type="button"
                    onClick={() => navigateTo(hit)}
                    className="flex w-full flex-col gap-0.5 px-3 py-2 text-left hover:bg-surface-2"
                  >
                    <span className="truncate text-sm font-medium">{hit.title}</span>
                    {(hit.subtitle || hit.snippet) && (
                      <span className="truncate text-xs text-muted">{hit.subtitle || hit.snippet}</span>
                    )}
                  </button>
                ))}
              </div>
            ) : null,
          )}
        </div>
      )}
    </div>
  );
}
