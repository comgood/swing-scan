<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Conventions

- FE lane owns `apps/web/**`; API types come only from `@swing-scan/api-client`, mocks from `contracts/mocks/`.
- Folder by feature: `src/features/<name>/`. Static export only (`output: "export"`), no server routes.
- WCAG AA, keyboard usable, layouts hold at 375 px (U-6). Map 422 errors to their fields (U-7).
- Commands: `make dev-web`, `pnpm --filter web lint`, `pnpm --filter web typecheck`, `pnpm --filter web format`.
- `typecheck` runs `next typegen` before `tsc`: `LayoutProps` and `PageProps` are generated into `.next/types/`, so plain `tsc` fails on a fresh checkout.
- Design system: build all UI to [`design.md`](design.md) (spec 0003); token values live in `src/app/globals.css`. Colours come from tokens only (`bg-primary`, `text-positive`), never hex or Tailwind palette classes; `src/raw-colours.test.ts` fails on any.
- Shared layers: `src/components/ui/` is generated shadcn `base-nova` (Base UI, so `render` not `asChild`); edit it only for tokens, focus or accessibility, and note the edit at the top of the file. App parts composed from it live in `src/components/` (the page frame in `src/components/shell/`), helpers in `src/lib/`.
- Add every new shared component to the hidden `/ui` gallery (`src/app/ui/gallery.tsx`, invented data in `sample.ts`, or a feature's own `<feature>-sample.ts` such as `exit-lab-sample.ts`); its test runs axe on each section, with a 20 s timeout because dense sections take about 5 s on the CI runner.
- Features so far, each imported through its folder's `index.ts`: `src/features/scan/` (the workspace on `/` with the rule builder mounted, `?template` and `?r=` links via `use-rule-link.ts`, results table; spec 0005), `src/features/rule-builder/` (the `RuleBuilder` component, its reducer, the `?r=` codec and the JSON panel; spec 0008) `src/features/backtest/` (the whole `/backtest` page: URL inputs, the exit form, the 2 to 6 config lab form in `lab-configs.tsx` and `exit-fields.tsx`, assumptions header, metrics, trade list; one or no exit config renders the portfolio report, 2 to 6 the exit lab, picked by the response's `mode`; specs 0007 and 0009) and `src/features/exit-lab/` (`ExitLabResults`: the IS and OOS table, edge and random rows, guide row and `ProcedureNote`, plus `DEFAULT_CONFIGS`; spec 0009, mounted by `features/backtest`).
- URL state changes use `history.replaceState`, not `useRouter().replace`, so components still work where no App Router is mounted (tests); see `use-rule-link.ts`.
- API calls use the one client `api` from `src/lib/api.ts` with TanStack Query. Never reuse the shell's `["health"]` query key. Errors go through `toApiError` and `ErrorState`, 422 bodies through `fieldErrorsFrom422` (the API keeps the operand's union tag in right side paths, e.g. `conditions.1.right.ind.n`; drop it with `withoutTag` from `src/lib/field-errors.ts`, owner ruling 2026-10-09), and every number on screen through `src/lib/format.ts`.
- Honesty guards live in `src/features/honesty/`: mount `<RunTrialCounter trial={result.trial} />` only once a 200 backtest result is on screen, with a stable `stores` object, and `<ProcedureNote />` right after the exit lab table (spec 0004).
- `tests/acceptance/` holds QA's Vitest UI acceptance tests (included in `vitest.config.mts`); the FE lane never edits them.
- TanStack Table is v9 (`useTable` with `tableFeatures`, not v8's `useReactTable`); its docs ship in `node_modules/@tanstack/react-table/skills/`.
- Tests: Vitest in jsdom, `*.test.ts(x)` beside the code, run with `pnpm --filter web test`. Helpers live in `src/test/` (`renderWithQuery`, `expectNoAxeViolations`); MSW answers every request and `healthHandler`, `scanHandler` and friends switch a route per test. jsdom applies no Tailwind CSS, so contrast, layout and real focus need a browser check.
