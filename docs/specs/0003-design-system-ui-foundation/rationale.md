# 0003 rationale: design system and UI foundation

The decision record for [index.md](index.md). `/develop` reads `index.md` and `apps/web/design.md`; this file is for you and for reviewers.

## Context

The web app today is the scaffold from spec 0001: one page, a hand written API status line, and the default Next.js globals (a white or black background, Arial on the body). Six later features (8 to 13) add real pages: the scan results, the rule builder, the backtest report, the exit lab, and the honesty guards. They are built in parallel lanes by agents working in separate worktrees. Without a shared visual language each agent will pick its own colours, spacing, input behaviour, and error display, and the product will look stitched together.

The criteria already set hard requirements on the UI: a synthetic market banner on first visit (U-1), a live mode warning on every page (U-2), a warm up state after 1.5 seconds (U-5), no horizontal scroll at 375 px with tables scrolling in their own box (U-6), and 422 errors shown on the offending field (U-7). `apps/web/AGENTS.md` adds WCAG AA and keyboard use. The stack is fixed by spec 0001: Next.js App Router with static export, Tailwind v4, shadcn/ui, TanStack Table and Query, Lightweight Charts. Spec 0002 fixes the API shapes, the 422 body, the `_pct` convention, `null` for undefined numbers, and MSW mocks in `apps/web/src/mocks/`.

The constraints are the project's: $0, about a week, a portfolio piece that a reviewer will click through, and a research tool whose credibility rests on numbers being easy to read and honesty notes being impossible to miss. There is no designer, no Figma file, and no screenshots. If this is not decided now, the first page built (feature 8) silently becomes the design system, and every later page copies whatever it happened to do.

## Options considered

### Option 1: shadcn/ui `base-nova` with our own tokens and a small set of app components (chosen)

Initialise shadcn/ui in `apps/web` with the CLI default preset (`base-nova`: Base UI primitives, nova style), replace its colour variables with tokens written for this app, and build only the parts the app needs that shadcn does not ship (shell, number input, data table wrapper, warm up notice, error state, 422 mapper, formatters). A hidden `/ui` gallery shows them all.

**Pros**:
- Matches the stack already chosen in spec 0001 and the installed `shadcn` and `tailwind-design-system` skills, so agents have docs and conventions on hand.
- The CLI default is the most travelled path today, so `/develop` follows documented steps.
- We own the code, so accessibility fixes and token changes are one edit.

**Cons**:
- Copied components drift from upstream; updates are manual.
- Base UI has fewer community examples than Radix.

### Option 2: shadcn/ui on Radix primitives (`radix-nova`)

The same as Option 1, but with Radix UI as the primitive layer.

**Pros**:
- Radix is older, with many more examples and answers online.
- `asChild` is the pattern most existing shadcn snippets use.

**Cons**:
- Not the CLI default any more, so fresh docs and new components target Base UI first.
- No feature here needs anything Radix has that Base UI lacks.

### Option 3: shadcn defaults with no custom design work

Run shadcn init and use its neutral theme as is, with no `design.md`, no custom tokens for gains, losses, or banners, and no gallery.

**Pros**:
- Fastest: about an hour less work.
- Nothing to maintain beyond the generated files.

**Cons**:
- No tokens for positive and negative values, warnings, or chart lines, so each page invents them.
- Contrast is not checked for the app's actual pairs, and nothing shows the components in one place for verification.

### Option 4: A finance terminal style (dark only, dense, coloured)

A dark, Bloomberg like interface with many accent colours and maximum density.

**Pros**:
- Looks "trading" at first glance in a portfolio.
- Very compact for large tables.

**Cons**:
- Signals live trading excitement, the opposite of the research honesty the product stands for.
- Dark only fails visitors who need light mode, and many accents make contrast and colour blind safety harder.

## Rationale

Option 1 wins because the forces here are speed, consistency across parallel agents, and credibility. Speed and consistency both come from using the stack exactly as spec 0001 chose it, through its default path, and writing down the few decisions that a default cannot make for this app: what colour a gain is, how a warning looks, how a number is typed and formatted, what happens on a 422 or a cold start. Those are exactly the places where parallel agents would otherwise diverge. Option 3 saves an hour now and costs it back many times over in features 8 to 13.

Base UI over Radix (Option 2) is a close call. The deciding force is that `/develop` reads current shadcn docs and the installed skill, which both lead with the `base-nova` default; choosing the default keeps generated code and docs in step. Radix remains a fine runner up, and switching later is a preset change, not a rewrite.

The calm research notebook direction over a terminal look (Option 4) follows from the product's purpose. The whole point of Swing Scan is to stop you fooling yourself, so the interface should slow you down slightly and make IS versus OOS, assumptions, and warnings legible, not exciting. Light and dark both ship because it costs little with tokens, and following the OS avoids a toggle that a static export would need extra script to do without a flash.

## Decision log: questions answered on your behalf

This spec was produced by a background `/architect` run that could not ask you questions. Each question the skill would have asked is listed with the choice made, why, and the alternatives, so you can confirm or change any of them. Change one by editing this list and the matching part of `index.md` or `design.md`, or rerun `/architect design system & UI foundation`.

| # | Question | Choice | Why | Alternatives |
|---|---|---|---|---|
| 1 | Overlap: is this a new spec or an update to 0001 or 0002? | New spec 0003 | 0001 picks the libraries, 0002 the data shapes; neither decides the look or components | Update 0001 in place |
| 2 | How should I get the design? | No design yet, propose a direction (written to `apps/web/design.md`) | No Figma file, screenshots, or `design.md` exist | A design tool via MCP (Figma) · screenshots you provide · the current scaffold UI |
| 3 | Visual direction | Calm research notebook: neutral zinc greys, one blue accent, dense tables, no decoration | Fits a research honesty product; keeps numbers and warnings prominent | shadcn defaults untouched · dark finance terminal · warm editorial "paper" look |
| 4 | Theme | Light and dark, following the OS, no toggle | Cheap with tokens; no flash and no stored preference on a static site | Light only · toggle with stored preference · dark only |
| 5 | Component base and preset | shadcn/ui `base-nova` (Base UI primitives) | The current CLI default, so docs and the installed skill match | `radix-nova` (Radix primitives) · another style (`vega`, `maia`, `lyra`, `mira`, `luma`) |
| 6 | Where components live | Inside `apps/web` (`src/components/ui/` and `src/components/`) | One app; a shared package adds workspace wiring and touches `packages/` | A shared `packages/ui` via the shadcn monorepo template |
| 7 | Accent colour | Blue (`#1d4ed8` light, `#60a5fa` dark) | Neutral meaning, distinct from gain and loss colours | Indigo · teal · no accent (monochrome) |
| 8 | Gain and loss colours | Green and red, always with a sign and never colour alone | Familiar to traders; the sign keeps it colour blind safe | Blue and orange · monochrome with signs only |
| 9 | Fonts | Geist Sans and Geist Mono (already loaded), `tabular-nums` for numbers | Already in the scaffold; good tabular figures | Inter · the system font stack |
| 10 | Density and base size | Compact: 14 px table and body text, 16 px inputs on phones | Data heavy screens; 16 px stops iOS zoom on focus | Comfortable 16 px everywhere |
| 11 | Which components belong to this feature | Shell, form parts, number input, data table, banners, badges, cards, loading, warm up, error and empty states, formatters, 422 mapper, gallery; tabs, tooltips, switches, and popups left to the feature that needs them | The shared parts doc 02 task W1 and the scope row list; page specific parts stay with their features | Also build builder rows and report parts now · build only primitives |
| 12 | Page layout | Header, banner slot, main capped at 1280 px, footer; sections stacked; page arrangement left to feature 8 | Enough structure for every page without guessing feature 8's layout | Fixed two column workspace now · full width |
| 13 | Data mode source for the banner | `GET /health` `data_mode`, defaulting to synthetic when unknown | The shell already pings `/health` to wake Lambda; `/meta.data` is null until feature 7 | `GET /meta` `data.data_mode` · a build time env var |
| 14 | Live badge wording (U-2 gives meaning, not words) | "Live data: current S&P 500 members only (survivors). Results are biased upward." | States the bias plainly | Shorter "Survivors only" badge · feature 13 decides later |
| 15 | Footer text | "Portfolio project. Not investment advice." | Required disclaimer, matches the scaffold wording | No footer · a longer disclaimer |
| 16 | Number input behaviour | Text input with `inputMode` and a local draft, strict number pattern on blur or Enter, range shown as a hint, never clamped (full rules in AC-6) | The server's 422 is the one source of range errors; native `type="number"` has poor parsing and scroll wheel bugs | Native `type="number"` · clamp to range · stepper buttons |
| 17 | Client side range checks | None; only "is it a number" | Avoids two sources of truth for ranges | Mirror the contract ranges in the client |
| 18 | 422 path format | `loc` without `"body"`, joined with `.` | Simple string keys that match form field names | Keep `loc` arrays · JSON Pointer paths |
| 19 | Data table | TanStack Table plus shadcn `Table`, sortable with `aria-sort`, scroll box, sticky header, optional 50 row pages, no virtualisation | At most 2,000 rows (spec 0002), so paging is enough | Virtualised rows · a grid library |
| 20 | Warm up notice text | "Warming up the engine…" after 1,500 ms, `role="status"` | U-5 wording and threshold | A progress bar · a toast |
| 21 | Error display | Inline `ErrorState` panel with "Try again"; 501 shows "Not built yet" with the server detail | Errors stay next to what failed; 501s are expected while features land | Toast notifications · a full page error |
| 22 | Toasts, tabs, tooltips, switches | None in this feature | No flow needs a transient message yet | Add the preset's toast now |
| 23 | Number formatting | `format.ts` with a fixed `en-US` locale, `n/a` for null, ASCII minus, no sign on a rounded zero | Same text in static HTML and browser; null is never shown as 0; ASCII minus copies and reads aloud reliably | Browser locale · `Intl` per call site |
| 24 | Accessibility checks | `axe-core` in Vitest per gallery section through a small helper (contrast, region, and main landmark rules off in jsdom), plus keyboard, 375 px, 320 px, focus, and contrast checks by hand in `/check verify` | Playwright is deferred (spec 0001); jsdom cannot test contrast, so the `design.md` table covers it | Playwright with axe · Storybook a11y addon |
| 25 | Component gallery | A `/ui` page, statically exported, `noindex`, not linked | Real pages do not exist yet; doubles as a portfolio piece | Storybook · no gallery |
| 26 | Motion | Fades of 150 ms at most, off under reduced motion | Calm direction; accessibility | No motion at all · preset defaults |
| 27 | Icons | lucide, as installed by the preset | Default of the preset; no extra choice to maintain | Heroicons · no icons |
| 28 | Chart colours | Fixed now as `chart-equity`, `chart-benchmark`, `chart-oos` tokens | Feature 9 then does not invent them | Leave to feature 9 |
| 29 | Build order | Tracer Bullet: tokens, preset, shell, ping, gallery, one test first; then forms, data display, feedback, hardening | The project's recorded approach | Build all primitives first, shell last |
| 30 | References section in the spec | None, keep it clean | The default for a feature spec; the reasoning stays here | Sources only · sources plus web links |
| 31 | Look for new Agent Skills or MCP servers? | No | `shadcn`, `tailwind-design-system`, and the shadcn MCP are already listed in `AGENTS.md`; no new tool category was chosen | Search the registries |
| 32 | Run a cross check of the spec by another model? | Yes, another model (read only) | Recommended at the Beta tier; it looks for values the spec never sources | Skip · same model |
| 33 | The cross check found gaps. How to proceed? | Apply the recommended fixes | Each fix closes a decision the builder would otherwise invent; all are listed below | Answer each one yourself · leave them for later |
| 34 | Accept the assembled spec? | Accepted as revised, status left `Proposed` | Status advances only when `/develop` builds it | Change parts before linking |

### Fixes applied from the cross check

The cross check (a read only pass on a different model) found these gaps. Each was closed with the recommended fix; change any you disagree with.

| # | Gap | Fix applied |
|---|---|---|
| C1 | shadcn's `dark:` classes rely on a `.dark` class we never set | Redefine the `dark` variant as a `prefers-color-scheme` media query; no `.dark` class anywhere (AC-1) |
| C2 | Preset variables not in `design.md` would bypass the contrast table | Delete unused ones, alias `popover` to `card`, replace `dark:bg-input/30` with `bg-transparent` (AC-1, `design.md`) |
| C3 | Native controls stay light in dark mode | `color-scheme: light dark` on `:root` (AC-1) |
| C4 | shadcn init rewrites `globals.css`, so tokens first would be lost | Build plan task 1 runs init first, then applies tokens |
| C5 | `max-w-screen-xl` does not exist in Tailwind v4 | Use `max-w-7xl` (1280 px) |
| C6 | The preset's 50% focus ring fails 3:1 and vanishes in forced colours | One global `:focus-visible` outline rule, preset ring classes removed (AC-13) |
| C7 | Health query details, status texts, MSW start order, warm up on cold start were open | 10 s timeout, one retry, key `["health"]`, exact status texts, MSW awaited before first render, shell `WarmupNotice` (AC-4) |
| C8 | Banner versus badge, roles, dismissal, placement | Both data mode texts use one `Banner` warning, not dismissible, no live role, placed as the first child of `main` so the skip link does not skip it (AC-3, AC-4, AC-11) |
| C9 | Skip link target, layout server versus client split | `main` has `tabIndex={-1}`; `layout.tsx` stays a server component; `/` keeps its intro text (AC-3) |
| C10 | Raw colour rule had no enforcement and collided with generated files | A Vitest check with exact patterns covering `src/components/ui/` too (AC-2) |
| C11 | Field wiring would fight Base UI; Select popup is painful in jsdom; loading button lost focus | Use the preset `Field`; native select; loading uses `aria-disabled` and keeps focus; icon buttons require a label (AC-5) |
| C12 | Number input parsing details | Strict pattern, draft text, resync rule, canonical text, error precedence, hint rules (AC-6) |
| C13 | 422 mapper edge cases and lookup helpers | Only `body` stripped, string `detail` to form, fallback message, `errorAt` and `errorsUnder` (AC-7) |
| C14 | Table sort order, nulls, sticky header, scroll box focus, pagination reset, highlight | All specified in AC-8, including `max-h-[70vh]` so the sticky header works |
| C15 | Warm up live region announced unreliably; `isPending` versus `isFetching` | Region always present; `isPending` only (AC-9) |
| C16 | How errors reach `ErrorState`; 501 retry; timeouts | `toApiError`, a timeout case, no retry on 501, `role="alert"` (AC-10) |
| C17 | Unused parts that add jsdom pain (tabs, tooltip, switch) | Dropped from this feature (AC-11) |
| C18 | Rounding to zero, minus sign, decimals, dates | Rounded zero has no sign, ASCII minus, `decimals` option, `formatDate` (AC-12) |
| C19 | Reduced motion had no mechanism | One global CSS rule (AC-13) |
| C20 | 320 px reflow, target size, `min-w-0` | Added to AC-14 and `design.md` |
| C21 | Gallery server and client split, sample data source, focus state | `page.tsx` plus `gallery.tsx` plus `sample.ts`; focus checked by hand (AC-15) |
| C22 | Test setup, axe helper, jsdom stubs, manual checklist | Named in AC-16 |
| C23 | Missing contrast pairs (accent hover, card, input on card) | Computed and added to `design.md` (all pass) |
| C24 | Failed ping on a local live run shows the synthetic banner | Accepted and recorded under Consequences |
