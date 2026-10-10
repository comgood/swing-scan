"use client";

// The header's page links (UAT: the app had no navigation and no way back from /backtest).
// A client island so `AppShell` stays a server component. `usePathname` is null outside the App
// Router (a component test with no router), and then no link is marked as the current page.
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { href: "/", label: "Screener" },
  { href: "/backtest", label: "Testing" },
] as const;

export function SiteNav() {
  const pathname = usePathname() as string | null;
  return (
    <nav aria-label="Pages" className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {NAV_ITEMS.map(({ href, label }) => {
        const current = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "rounded-md text-sm font-medium text-muted-foreground hover:text-foreground",
              current && "text-foreground underline underline-offset-4",
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
