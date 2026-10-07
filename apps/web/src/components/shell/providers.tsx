"use client";

// One QueryClient per page load, and the MSW worker awaited first in mock mode (spec 0003 AC-4).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { MockProvider } from "@/mocks/mock-provider";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <MockProvider>{children}</MockProvider>
    </QueryClientProvider>
  );
}
