// Renders a component inside a fresh QueryClient, as Providers does in the app.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";

export function renderWithQuery(ui: ReactElement): RenderResult {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
