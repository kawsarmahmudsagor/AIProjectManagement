// Backend codes that get a dedicated blocking popup instead of (or on top of) the
// usual inline error handling — see backend/app/providers/gemini.py's _classify_error.
export type ProviderErrorKind = "limit" | "expired";

const KIND_BY_CODE: Record<string, ProviderErrorKind> = {
  RATE_LIMITED: "limit",
  PROVIDER_KEY_EXPIRED: "expired",
};

export function providerErrorKind(code: string | undefined | null): ProviderErrorKind | null {
  return code ? (KIND_BY_CODE[code] ?? null) : null;
}

function displayProviderName(provider: string | null | undefined): string {
  if (!provider) return "AI provider";
  return provider.charAt(0).toUpperCase() + provider.slice(1);
}

export function providerErrorMessage(kind: ProviderErrorKind, provider: string | null | undefined): string {
  const name = displayProviderName(provider);
  return kind === "limit"
    ? `You have reached your ${name} API limit. Please top up or use a different API key.`
    : `Your ${name} API key has expired. Please use a different API key.`;
}
