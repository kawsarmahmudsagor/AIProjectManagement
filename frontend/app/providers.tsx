"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ProviderErrorModalProvider } from "@/components/layout/provider-error-modal";
import { ToasterProvider } from "@/components/ui/toaster";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ProviderErrorModalProvider>
        <ToasterProvider>{children}</ToasterProvider>
      </ProviderErrorModalProvider>
    </QueryClientProvider>
  );
}
