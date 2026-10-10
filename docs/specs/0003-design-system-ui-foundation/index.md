# 0003. Build the UI foundation on shadcn/ui with a calm, token based design system

**Date**: 2026-10-07
**Status**: Accepted

## Summary

This spec sets the look and the base building blocks of the web app before any real page is built. You get a quiet "research notebook" style: neutral greys, one blue accent, light and dark themes that follow your operating system, and every colour pair checked for readable contrast. The components come from shadcn/ui (a set of copy in React components you own and edit), using its default `base-nova` preset, plus a few app parts of our own: the page shell with the data mode banner, a number input, a sortable data table, the "Starting the engine" notice, error and empty states, and a helper that puts 422 validation errors on the right field. A hidden `/ui` gallery page shows every part in every state so it can be checked by keyboard, at 375 px, and with an automated accessibility scan.

## Requirements

**User stories**:
- As the FE lane, I want ready, accessible base components and fixed design tokens so that the scan, backtest, and exit lab pages (features 8 to 13) are assembled, not designed, and look like one product.
- As a visitor on a phone, I want the page to fit a 375 px screen without sideways scrolling so that I can read results anywhere (U-6).
- As a keyboard or screen reader user, I want every control labelled and reachable with a visible focus ring so that I can use the whole tool without a mouse.
- As a visitor, I want to see at a glance that the market is synthetic, and that a slow first request is the engine waking up, so that I trust what I see (U-1, U-5).
- As the owner, I want one place that shows every component in every state so that `/check verify` and the portfolio reviewer can see the system working.

**Acceptance criteria**:
- **AC-1**: `src/app/globals.css` defines every colour token in `apps/web/design.md` for light (`:root`) and dark (`@media (prefers-color-scheme: dark)`), plus `--radius`, maps them through `@theme inline`, and sets `color-scheme: light dark` on `:root`. The `dark` variant is redefined as `@custom-variant dark (@media (prefers-color-scheme: dark));` so every `dark:` class in generated code follows the OS, and no `.dark` class is used anywhere. After shadcn init, preset variables that `design.md` does not name are deleted (`sidebar-*`, `chart-1` to `chart-5`), except `popover` and `popover-foreground`, which alias `card` and `card-foreground`. The page follows the OS theme with no toggle and no flash of the wrong theme. The body uses Geist Sans (the `Arial` rule is gone, `font-sans` is set once on `html`).
- **AC-2**: shadcn/ui is initialised in `apps/web` with the `base-nova` preset (`components.json` present, `base` set to `base`). Generated primitives live in `src/components/ui/`, shared app components in `src/components/`, helpers in `src/lib/`. No `.ts` or `.tsx` file under `src/` (including `src/components/ui/`, excluding `*.test.tsx`) contains a raw colour: a Vitest check fails on any match of `#[0-9a-fA-F]{3,8}\b`, `rgb\(`, `hsl\(`, `oklch\(`, or a Tailwind palette class (`\b(bg|text|border|ring|fill|stroke|from|to|outline)-(white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)\b`). Generated files are edited to use tokens instead.
- **AC-3**: `AppShell` renders, in order: a "Skip to content" link (the first Tab stop, `sr-only` until focused, then visible at the top left), a header with the product name (a link to `/`) and `ApiStatus`, then `<main id="main" tabIndex={-1}>` capped at 1280 px (`max-w-7xl`) whose first child is the data mode banner, then a footer reading "Portfolio project. Not investment advice." The body is a full height column so the footer sits at the bottom of short pages. The header is not sticky. `src/app/layout.tsx` stays a server component (it exports `metadata`) and renders `AppShell` around every page; `Providers` and `ApiStatus` are client components inside it. `/` keeps the scaffold intro text inside the shell, without the old status line, until feature 8 replaces it.
- **AC-4**: The shell runs one health query (`queryKey: ["health"]`, `GET /api/v1/health` through the generated client, 10 s timeout, `retry: 1`, `staleTime: Infinity`) on load; it also wakes a cold Lambda. `ApiStatus` shows "Checking the API…" while pending, "API ready (data: {data_mode}, version {version})" on success, and "API not reachable" on failure. The data mode banner is a `Banner` with `variant="warning"`, not dismissible, and shows "Made up market: not real prices" unless `data_mode` is exactly `"live"`, including in the static HTML, while pending, and after a failure. When `data_mode` is exactly `"live"` the same banner instead reads "Live data: current S&P 500 members only (survivors). Results are biased upward." on every page (U-1 banner part, U-2). The shell renders a `WarmupNotice` bound to the health query, so a cold start shows the notice. With `NEXT_PUBLIC_API_MOCK=1`, the MSW browser worker is started and awaited before `Providers` renders its children, so the first query hits the mocks.
- **AC-5**: Form parts exist and are labelled: the preset's `Field` (with `FieldLabel`, `FieldDescription`, `FieldError`), `Input`, `Label`, `Checkbox`, a styled native `<select>` (`NativeSelect`, not the Base UI popup select), `Button` (variants `default`, `secondary`, `outline`, `ghost`, `destructive` as a solid `destructive` fill with `destructive-foreground` text; sizes `sm`, `default`, `icon`), and `FormRow` (`columns: 1 | 2 | 3 | 4`, a grid that stacks to one column below 640 px, every child `min-w-0`). Ids come from `React.useId`; `Field` wires `aria-invalid` and `aria-describedby` (description and error both listed) through Base UI's field context, so app code does not set them by hand. `FieldError` shows in `destructive` colour with a lucide `CircleAlert` icon marked `aria-hidden`. `Button` with `loading` sets `aria-disabled="true"` and `aria-busy="true"`, ignores clicks, keeps focus, and overlays a spinner on its label (the label stays rendered and invisible, so the width holds). `size="icon"` requires an `aria-label` through the prop types.
- **AC-6**: `NumberInput` is a text input with `inputMode="decimal"` (or `"numeric"` when `integer`) that keeps its own draft text. On blur and on Enter it trims the text and commits: empty gives `null`; text matching `^-?(\d+\.?\d*|\.\d+)$` gives that number (`-0` gives `0`); anything else (`abc`, `1e3`, `1,000`, `+5`, `Infinity`) keeps the draft, emits nothing, and shows "Enter a number". With `integer`, a value that is not a whole number (`2.5`, but not `2.0`) shows "Enter a whole number". It emits `onValueChange` only when the committed value differs from `value`, then shows the canonical text (`String(n)`, so `2.50` becomes `2.5`). Enter commits and does not block form submit. A local error clears as soon as the text is edited. When `value` changes from outside while the input is not focused (for example a template load), the draft is replaced. With both `min` and `max` it shows the hint "Allowed: {min} to {max}" (plain `String` of each); with only one, no hint. It never clamps or rejects an in format value that is out of range (the server's 422 owns range errors). A local parse error replaces a server error passed in `error`; the hint stays visible in both cases.
- **AC-7**: `fieldErrorsFrom422(body)` takes FastAPI's 422 body (`{"detail": [{"type", "loc", "msg", "input", "ctx"}]}`) and returns `{ fields: Record<string, string>, form: string[] }`. The key is `loc` with a leading `"body"` removed (other prefixes such as `"query"` are kept), joined with `.` (so `["body","rule","conditions",2,"left","n"]` becomes `rule.conditions.2.left.n`). The message is `msg` with its first letter capitalised (spec 0002's custom errors read "must be between {min} and {max}"). An error whose `loc` is only `["body"]` goes to `form`; a `detail` that is a string becomes `form: [detail]`; any other shape becomes `form: ["The request was rejected."]`. When two errors share a key, the first wins; `form` drops exact duplicates. `errorAt(errors, path)` returns the exact match, and `errorsUnder(errors, prefix)` returns every entry at or below a prefix (for a row that shows its children's errors). `FormErrorSummary` lists `form` errors in a `role="alert"` region (U-7 foundation).
- **AC-8**: `DataTable` wraps TanStack Table with the shadcn `Table` markup. Each sortable header holds a `<button>`; the `th` carries `aria-sort` (`ascending`, `descending`, or `none`). The first click sorts numeric columns (`meta.numeric: true`) descending and text columns ascending, the second reverses, the third clears. `null` values sort last in both directions; text compares with `localeCompare(…, "en-US", { sensitivity: "base" })`; ties keep input order. The sort icon is `aria-hidden`. Numeric columns, including their `n/a` cells, are right aligned with `tabular-nums`. A column may set `meta.highlight(row)`; true paints that cell with `bg-accent` (the "best IS" marker). The table sits in a scroll box (`overflow-auto`, `max-h-[70vh]`, `tabIndex={0}`, `role="region"`, `aria-label` set to the caption) with a sticky header, so a wide table never widens the page. `caption` is required and `sr-only` unless `captionVisible`. `getRowId` is required. An `empty` node shows when there are no rows. With `pageSize` set (50 by default when paginated), Previous and Next buttons and "Page X of Y" show only when there is more than one page, the buttons are disabled at the ends, and the page resets to 1 when the sort or the data changes.
- **AC-9**: `WarmupNotice` takes `pending: boolean` (callers pass TanStack Query's `isPending`, never `isFetching`, so a background refetch never shows it). Its `role="status"` `aria-live="polite"` region is always in the DOM and empty until `pending` has been true for 1,500 ms; then it holds "Warming up the engine…" (with the U+2026 ellipsis) and an `aria-hidden` spinner. It empties as soon as `pending` is false, and the timer restarts on the next request (U-5). The caller places it next to the content it waits for.
- **AC-10**: `toApiError(result)` in `src/lib/api-error.ts` turns an `openapi-fetch` result or a thrown fetch error into `ApiError`. `ErrorState` takes an `ApiError` and an optional `onRetry`, renders a `Banner variant="danger"` (`role="alert"`) with a heading level set by a `headingLevel` prop (default 2), and shows: network failure, "Can't reach the engine" / "Check your connection and try again."; 501, "Not built yet" / the server's `detail` when it is a string; 504 or a timeout, "The engine took too long" / "It may be starting up. Try again."; any other status, "Something went wrong" / "The API answered with status {status}." A "Try again" button calling `onRetry` shows for every case except 501. 422s never reach `ErrorState`; they go to fields (AC-7).
- **AC-11**: `Banner` (built on shadcn `Alert`, not closable) has variants `info` (lucide `Info`), `warning` (`TriangleAlert`), and `danger` (`CircleAlert`), each icon `aria-hidden` beside text that wraps (`break-words`). `info` and `warning` carry no live role (they are static page content); `danger` uses `role="alert"` and is only inserted when an error happens. `Badge` has variants `default`, `secondary`, `outline`, `positive`, `negative`, `warning`, `info`. `Skeleton` is `aria-hidden`. `EmptyState` (title plus one line hint) is built on the preset's `Empty`. `Card` and `Separator` come from the preset. Tabs, tooltips, switches, and popups are left to the feature that first needs them.
- **AC-12**: `src/lib/format.ts` exports, all with a fixed `en-US` locale and `n/a` for `null`, `undefined`, `NaN`, or an infinite value: `formatPct(v, { decimals = 2 })` (`3.254` gives `+3.25%`, `-1.1` gives `-1.10%`, and a value that rounds to zero gives `0.00%` with no sign); `formatNumber(v, { decimals = 2 })` with thousands separators; `formatR(v)` (`1.32R`, `-0.50R`); `formatPrice(v)` (2 decimals, thousands separators, no currency symbol); `formatInt(v)` (rounded, separators); `formatDate(s)` (returns the API's `YYYY-MM-DD` unchanged). Negative numbers use the ASCII hyphen minus, which copies and reads aloud reliably. Percent inputs are already percent numbers (fields ending `_pct`, spec 0002), so `formatPct` never multiplies by 100. `SignedValue` takes `value` and `format: "pct" | "r" | "number"` and renders the formatted text in `positive` or `negative` colour, `foreground` when it rounds to zero, with the sign always shown for non zero values.
- **AC-13**: Every interactive part is reachable with Tab in visual order, works with Enter or Space (and arrow keys where the Base UI primitive provides them), and has no keyboard trap. Focus is one global rule, `:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }`, and the preset's `focus-visible:ring-*` classes are removed, so the ring stays at full contrast and survives Windows forced colours. Under `prefers-reduced-motion: reduce` a global rule cuts animation and transition durations to near zero; the spinner then stands still, which is fine because the text carries the meaning.
- **AC-14**: At 375 px and at 320 px wide the `/ui` gallery and the shell have no horizontal page scroll, `FormRow` stacks to one column below 640 px, and wide tables scroll inside their own box (U-6). Controls are at least 32 px tall (the preset's `sm`), above the 24 px WCAG 2.2 target size.
- **AC-15**: The `/ui` page renders inside the shell and shows every part from AC-3 to AC-12 in each state that can be shown statically (default, disabled, error, loading, empty, and for the table sorted and paginated); focus is checked by hand. `src/app/ui/page.tsx` is a server component that exports `metadata` with `robots: { index: false }` and renders a client `Gallery` from `src/app/ui/gallery.tsx`, which takes invented sample data from `src/app/ui/sample.ts` (never the API mocks). It is statically exported and not linked from the header.
- **AC-16**: Vitest with Testing Library, in `*.test.tsx` files next to the code, covers: `NumberInput` parsing (AC-6), `fieldErrorsFrom422`, `errorAt`, `errorsUnder` (AC-7), `DataTable` sorting, null order, `aria-sort`, and page reset (AC-8), `WarmupNotice` timing tested directly with a `pending` prop and fake timers (AC-9), `toApiError` and the `ErrorState` cases (AC-10), `Banner` roles (AC-11), the formatters (AC-12), `Button` loading and `Field` error wiring (AC-5), the raw colour check (AC-2), and the shell banner choice (AC-4, with MSW returning `synthetic`, `live`, and a network error). A helper `expectNoAxeViolations(container)` runs `axe-core` with `color-contrast`, `region`, and `landmark-one-main` disabled (jsdom has no layout, and fragments have no landmarks), and every gallery section passes it. The Vitest setup file stubs what Base UI needs and jsdom lacks (`ResizeObserver`, `matchMedia`, `PointerEvent`, `Element.prototype.scrollIntoView`). Keyboard order (AC-13), 375 px and 320 px layout (AC-14), focus visibility, and real contrast are checked by hand in a browser during `/check verify`, using the gallery.

## Decision

**Chosen option**: Option 1: shadcn/ui `base-nova` copied into `apps/web`, themed by our own CSS variable tokens recorded in `apps/web/design.md`, plus a small set of app components (see `rationale.md`).

Use the shadcn/ui CLI default preset as the component base, own the colours and type through tokens in `globals.css`, and build only the app specific parts (shell, number input, data table, warm up, errors, formatting) ourselves.

**Implementation skills**: `shadcn` (`shadcn-ui/ui`, `.agents/skills/shadcn/`) · `tailwind-design-system` (`wshobson/agents`, `.claude/skills/tailwind-design-system/`) · `nextjs-app-router-patterns` (`wshobson/agents`, `.claude/skills/nextjs-app-router-patterns/`) · `vercel-react-best-practices` (`vercel-labs/agent-skills`, `.claude/skills/vercel-react-best-practices/`)

**Design source**: `apps/web/design.md` (no Figma file or screenshots exist; the direction was proposed in this spec).

## Rationale

Reasoning, options, and every choice made on your behalf: see [rationale.md](rationale.md).

## Feature design

**Data model sketch**: no persisted data. The only shapes are props and helper types, all in the web app:

| Type | Fields | Notes |
|---|---|---|
| `DataMode` | `"synthetic" \| "live"` | from `GET /health` `data_mode`; only the exact string `"live"` counts as live |
| `FieldErrors` | `fields: Record<string, string>` · `form: string[]` | output of `fieldErrorsFrom422` |
| `NumberInputProps` | `value: number \| null` · `onValueChange(n: number \| null)` · `min?` · `max?` · `integer?` · `error?: string` · `label` · `hint?` | controlled value, local draft text |
| `DataTableProps<T>` | `columns: ColumnDef<T>[]` · `data: T[]` · `getRowId(row: T): string` · `caption: string` · `captionVisible?` · `initialSort?` · `pageSize?: number` (unset means no pagination) · `empty?: ReactNode` | column `meta`: `numeric?: boolean`, `highlight?(row: T): boolean` |
| `ApiError` | `{ kind: "network" } \| { kind: "timeout" } \| { kind: "http", status: number, detail?: string }` | built by `toApiError`; `detail` kept only when the body's `detail` is a string |

**State transitions** (`WarmupNotice`): `idle` (not pending) → `waiting` (pending, under 1,500 ms, region empty) → `warming` (pending, 1,500 ms or more, region shows the notice) → `idle` when pending ends. Leaving `waiting` or `warming` always clears the timer.

**Component inventory** (what this feature builds; page specific parts belong to later features):

| Part | Source | Lives in |
|---|---|---|
| Button, Input, Label, Field, Checkbox, NativeSelect, Table, Alert, Badge, Skeleton, Empty, Card, Separator, Spinner | shadcn `base-nova` (edited to tokens) | `src/components/ui/` |
| `AppShell`, `Providers`, `DataModeBanner`, `ApiStatus` (moved from `src/app/api-status.tsx`) | new | `src/components/shell/` |
| `Banner`, `FormRow`, `FormErrorSummary`, `NumberInput`, `DataTable`, `WarmupNotice`, `ErrorState`, `EmptyState`, `SignedValue` | new, composed from the primitives | `src/components/` |
| `fieldErrorsFrom422`, `errorAt`, `errorsUnder`, `toApiError`, `format.ts`, `cn` (from the preset) | new | `src/lib/` |
| `/ui` gallery | new page | `src/app/ui/page.tsx`, `gallery.tsx`, `sample.ts` |

Not in this feature: builder rows and the JSON panel (feature 10), the results table columns (feature 8), the report, assumptions header, and chart (feature 9), the exit lab table (feature 12), the trial counter and procedure note (feature 13).

**API surface** (what the foundation calls; all shapes from `@swing-scan/api-client`):

| Endpoint | Method | Key inputs | Key outputs | Auth | Key errors |
|---|---|---|---|---|---|
| `/api/v1/health` | GET | none | `status`, `data_mode`, `version` | public | timeout after 10 s or network failure: one retry, then "API not reachable" and the synthetic banner; no further retries |

Calls go through the generated `openapi-fetch` client and TanStack Query (spec 0001), with MSW serving mocks when `NEXT_PUBLIC_API_MOCK=1` and in Vitest (spec 0002). One `QueryClient` lives in `Providers`, created once per page load. Later features use their own query keys (`["meta"]`, `["scan", …]`) and never reuse `["health"]`.

**Value sourcing**:

| Action | Value produced or displayed | Source |
|---|---|---|
| shell | data mode (which banner text) | `GET /api/v1/health` `data_mode`; exactly `"live"` means live, everything else (pending, error, other value) means synthetic. The public demo is always synthetic and live runs only on localhost (D-5), so the fallback is never wrong in public. The shell banner is the one global data mode signal; reports show their own `assumptions.data_mode` (U-3) |
| shell | synthetic banner text | U-1, word for word: "Made up market: not real prices" |
| shell | live banner text | decided here (U-2 names the meaning, not the words): "Live data: current S&P 500 members only (survivors). Results are biased upward." |
| shell | API status text | decided here: "Checking the API…", "API ready (data: {data_mode}, version {version})", "API not reachable"; values from `/health` |
| shell | health timeout, retries | decided here: 10 s, one retry, TanStack's default retry delay |
| shell | footer text | decided here: "Portfolio project. Not investment advice." |
| `WarmupNotice` | 1,500 ms threshold, notice text | U-5 (threshold); text "Warming up the engine…" decided here from U-5's wording |
| `WarmupNotice` | `pending` | the caller's TanStack Query `isPending` flag |
| `NumberInput` | `min`, `max` for the hint | props from the caller; callers take them from `GET /indicators` (`n_min`, `n_max`) or the contract bounds in spec 0002 |
| `fieldErrorsFrom422` | field path and message | the 422 body's `loc` and `msg` (spec 0002, *Validation errors*) |
| `ErrorState` | status, 501 message | `toApiError` from the response status and string `detail` (spec 0002, AC-6) |
| `formatPct` | percent value | `_pct` fields, already in percent (spec 0002, AC-14) |
| `DataTable` | `n/a` cells | `null` values from the API (spec 0002, AC-14) |
| `DataTable` | "best IS" highlight | the caller's `meta.highlight`, fed from `best_is` in the trade lab response (spec 0002) |
| all parts | colours, sizes, radius, fonts | `apps/web/design.md` tokens |

**Key invariants**:
- Colours come only from tokens. Changing a token in `globals.css` and `design.md` changes the whole app; no component hard codes a colour (enforced by the AC-2 check).
- Colour never carries meaning alone: signs on numbers, icons and words on banners, text on errors.
- The synthetic banner is never hidden on the public site. The static HTML always contains it, and it changes to the live text only after the health ping says exactly `"live"`.
- The client never enforces a range. It checks only that a number is a number; the server's 422 is the one source of range errors, so the two cannot disagree.
- Every number on screen goes through `format.ts`, with the fixed `en-US` locale, so the static HTML and the browser render the same text.
- `src/components/ui/` holds generated shadcn code. Edit it only to apply tokens, remove the preset focus rings, or fix accessibility, and note the edit at the top of the file.

**Security model**: no auth and no user data (spec 0001). The only user input is rule and exit values, sent to the public API. Never render server text with `dangerouslySetInnerHTML`; error messages and `detail` render as plain text. The `/ui` page shows only invented sample data.

**Configuration required**: none new. Uses `NEXT_PUBLIC_API_URL` (spec 0001) and `NEXT_PUBLIC_API_MOCK` (spec 0002).

**New dependencies** (added by `/develop` in `apps/web/package.json`): what the shadcn `base-nova` init installs (Base UI, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `tw-animate-css`), `@tanstack/react-table`, `@tanstack/react-query` (if feature 3 has not added it), and for tests `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `axe-core`. Vitest, jsdom, and MSW arrive with feature 3.

**Critical test scenarios**:
- Happy path: the shell loads with MSW returning `data_mode: "synthetic"`, shows the synthetic banner and "API ready", and the gallery passes axe, verifies **AC-3**, **AC-4**, **AC-16**
- Live mode: MSW returns `data_mode: "live"`, the banner switches to the live text, verifies **AC-4**
- Failure case: the health ping fails twice, the synthetic banner stays and the status reads "API not reachable", verifies **AC-4**
- Slow request: with fake timers, `pending` true for 1,499 ms leaves the region empty, at 1,500 ms the notice appears, and it empties when `pending` goes false, verifies **AC-9**
- 422 mapping: the `422.rule.n_out_of_range.json` mock maps to `rule.conditions.N.left.n` with "Must be between …", a string `detail` lands in `form`, verifies **AC-7**
- Number entry: `abc` and `1e3` show "Enter a number" and emit nothing; `2.5` in integer mode shows "Enter a whole number"; `999` with `max` 260 emits 999 unchanged, verifies **AC-6**
- Table: sorting a numeric column with nulls puts nulls last both ways and sets `aria-sort`, and sorting returns to page 1, verifies **AC-8**
- Errors: a 501 shows "Not built yet" with the detail and no "Try again"; a network error shows "Try again", verifies **AC-10**
- Mobile: at 375 px and 320 px the gallery has no horizontal scroll and a 12 column table scrolls inside its box (manual in `/check verify`), verifies **AC-14**
- Auth or permission: not applicable, the app is public with no accounts (spec 0001).

## Build plan

Tracer Bullet: first one thin thread through the preset, tokens, the shell, the API ping, the gallery, and a test, then thicken one group of parts at a time. Start after feature 3's thin thread has merged (generated client, MSW, Vitest); until then tasks 1 and 2 can be built and their tests added once Vitest lands.

1. **Thread.** Run shadcn init with `base-nova` in `apps/web` (not the monorepo template, so components stay in the app). Then, because init rewrites `globals.css`, apply the tokens from `design.md` over it: light and dark values, `color-scheme`, the media query `dark` variant, aliases for `popover`, deletion of unused preset variables, the global focus and reduced motion rules, and removal of `Arial`. Add `Button`. Build `Providers` (one `QueryClient`, the awaited MSW worker in mock mode), `AppShell` with the skip link, header, `ApiStatus` moved in and switched to the generated client plus TanStack Query, `DataModeBanner`, the shell `WarmupNotice`, and the footer; update `layout.tsx` and `page.tsx`. Add the `/ui` page (`page.tsx`, `gallery.tsx`, `sample.ts`) showing `Button`. Add the Vitest setup stubs, `expectNoAxeViolations`, the raw colour check, and the banner choice test. Satisfies **AC-1**, **AC-2**, **AC-3**, **AC-4**, **AC-15**, **AC-16**
2. **Forms.** Add `Field`, `Input`, `Label`, `Checkbox`, `NativeSelect`, `FormRow`, `NumberInput`, `fieldErrorsFrom422` with `errorAt` and `errorsUnder`, `FormErrorSummary`, and the `Button` loading state, each in the gallery with its tests. Satisfies **AC-5**, **AC-6**, **AC-7**, **AC-15**, **AC-16**
3. **Data display.** Add `format.ts`, `SignedValue`, `Table`, `DataTable` (sort rules, `aria-sort`, `n/a`, highlight, scroll box with sticky header, pagination, empty slot), `Badge`, `Card`, `Separator`, `EmptyState`, with gallery sections and tests. Satisfies **AC-8**, **AC-11**, **AC-12**, **AC-15**, **AC-16**
4. **Feedback.** Add `Banner`, `Skeleton`, `Spinner`, `WarmupNotice` (the shell already uses a first version), `toApiError`, and `ErrorState`, with gallery sections and tests. Satisfies **AC-9**, **AC-10**, **AC-11**, **AC-15**, **AC-16**
5. **Hardening.** Walk the gallery by keyboard and at 375 px and 320 px, fix focus order, traps, and overflow; make every gallery section pass axe; confirm the raw colour check is green across `src/components/ui/`. Satisfies **AC-2**, **AC-13**, **AC-14**, **AC-16**

## Consequences

**Positive**:
- Features 8 to 13 assemble pages from tested parts, so FE work in the lanes is mostly wiring, not styling.
- The look, contrast, and copy rules are written down once in `design.md`, so parallel agents produce one consistent product.
- Accessibility is designed in (labels, focus, contrast table, axe in CI), which is cheaper than fixing it page by page.

**Negative / tradeoffs**:
- shadcn code is copied in and then edited (tokens, focus rule), so upstream fixes do not arrive automatically and a CLI update needs a careful diff.
- Base UI is newer than Radix, so fewer examples on the web use it (the shadcn skill covers the API differences, for example `render` instead of `asChild`), and it needs jsdom stubs in tests.
- No theme toggle: a visitor who wants dark mode on a light OS cannot switch.
- A failed health ping on a local live run shows the synthetic banner, which is wrong in that one case; accepted because nothing else works without the API either.
- The gallery page ships publicly (hidden, `noindex`); it is a small extra page to keep current.
- jsdom cannot check colour contrast, layout, or real focus order, so those rely on the `design.md` table and a manual browser pass.

**Neutral**:
- `src/app/api-status.tsx` moves into the shell and switches from raw `fetch` to the generated client.
- Lightweight Charts colours are fixed here (`chart-*` tokens) but the chart itself and its attribution arrive with feature 9.

## Follow-up

- [ ] `apps/web/AGENTS.md` should gain a pointer to `apps/web/design.md` and the rule "colours from tokens only" (for `/sync` after the build).
- [ ] Feature 13 owns the trial counter and procedure note; it reuses `Banner` and must keep the U-4 and U-8 copy word for word.
- [ ] Playwright is deferred (spec 0001). If it is added later, move the 375 px, focus, and contrast checks from manual `/check verify` into an automated browser test.
- [ ] Connect the shadcn/ui MCP server if you have not yet (spec 0001 follow up); `/develop` uses it to look up `base-nova` component docs.
