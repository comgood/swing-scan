// The page frame every route renders inside (spec 0003 AC-3): skip link, header, main with the
// data mode banner first, footer. A server component; the live parts are client islands.
import Link from "next/link";
import type { ReactNode } from "react";

import { ApiStatus } from "./api-status";
import { DataModeBanner } from "./data-mode-banner";
import { ShellWarmup } from "./shell-warmup";
import { SiteNav } from "./site-nav";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 md:px-6">
          <Link href="/" className="text-base font-semibold">
            Swing Scan
          </Link>
          <SiteNav />
          <ApiStatus />
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto flex w-full max-w-7xl min-w-0 flex-1 flex-col px-4 py-6 md:px-6"
      >
        <DataModeBanner />
        <ShellWarmup />
        <div className="mt-6 flex min-w-0 flex-col gap-8">{children}</div>
      </main>
      <footer className="border-t">
        <p className="mx-auto w-full max-w-7xl px-4 py-4 text-xs text-muted-foreground md:px-6">
          Portfolio project. Not investment advice.
        </p>
      </footer>
    </>
  );
}
