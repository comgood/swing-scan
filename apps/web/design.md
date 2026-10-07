# Swing Scan design system

The visual source of truth for `apps/web`. Decided in [spec 0003](../../docs/specs/0003-design-system-ui-foundation/index.md). If a page needs something this file does not cover, add it here first (through `/architect` when it changes the look), then build it. Never invent a colour, size, or component style in a page.

## Direction: a calm research notebook

Swing Scan is a research tool, not a trading terminal. The look should feel quiet and trustworthy so the numbers and the honesty notes carry the page.

- Neutral greys (zinc) for almost everything. One restrained blue accent for actions, focus, and the "best IS" highlight.
- Dense but readable: compact tables and controls, generous line height in prose.
- No gradients, no glow, no decorative imagery, no animation beyond short state fades.
- Gains and losses use green and red, but colour never carries meaning alone: every signed number shows its sign (`+3.25%`, `-1.10%`, with the plain ASCII minus), and every banner has an icon and words.
- Honesty copy (banners, assumptions, notes) is never hidden, collapsed by default, or styled to look like fine print.

## Theme

Light and dark both ship. The page follows your operating system setting (`prefers-color-scheme`). There is no toggle, so there is no stored preference and no flash of the wrong theme on a static page.

- `:root` sets `color-scheme: light dark`, so scrollbars and native controls follow the theme too.
- The Tailwind `dark` variant is redefined as `@custom-variant dark (@media (prefers-color-scheme: dark));`. No `.dark` class is ever used.

## Colour tokens

After shadcn init, delete preset variables this table does not name (`sidebar-*`, `chart-1` to `chart-5`). Defined once in `src/app/globals.css` as CSS variables on `:root`, redefined inside `@media (prefers-color-scheme: dark)`, and exposed to Tailwind through `@theme inline`. Components use the Tailwind names (`bg-background`, `text-muted-foreground`, `text-positive`), never raw hex values or Tailwind palette classes (`text-red-600`).

| Token                            | Light                               | Dark                  | Use                                             |
| -------------------------------- | ----------------------------------- | --------------------- | ----------------------------------------------- |
| `background`                     | `#ffffff`                           | `#09090b`             | page                                            |
| `foreground`                     | `#18181b`                           | `#fafafa`             | body text                                       |
| `card`                           | `#ffffff`                           | `#0f0f12`             | panels, table body                              |
| `card-foreground`                | `#18181b`                           | `#fafafa`             | text on panels                                  |
| `popover` / `popover-foreground` | alias of `card` / `card-foreground` | same                  | menus and popups from the preset                |
| `muted`                          | `#f4f4f5`                           | `#18181b`             | table header, skeleton, subtle fills            |
| `muted-foreground`               | `#52525b`                           | `#a1a1aa`             | hints, captions, secondary text                 |
| `secondary`                      | `#f4f4f5`                           | `#27272a`             | secondary button                                |
| `secondary-foreground`           | `#18181b`                           | `#fafafa`             | text on secondary                               |
| `primary`                        | `#1d4ed8`                           | `#60a5fa`             | primary button, links, active sort              |
| `primary-foreground`             | `#ffffff`                           | `#09090b`             | text on primary                                 |
| `accent`                         | `#eff6ff`                           | `#172554`             | hover fill, "best IS" cell highlight            |
| `accent-foreground`              | `#18181b`                           | `#fafafa`             | text on accent                                  |
| `destructive`                    | `#b91c1c`                           | `#f87171`             | solid destructive button fill, field error text |
| `destructive-foreground`         | `#ffffff`                           | `#09090b`             | text on destructive                             |
| `border`                         | `#e4e4e7`                           | `#27272a`             | dividers, card edges (decorative)               |
| `input`                          | `#71717a`                           | `#71717a`             | form control borders (must stay 3:1)            |
| `ring`                           | `#2563eb`                           | `#60a5fa`             | focus ring                                      |
| `positive`                       | `#15803d`                           | `#4ade80`             | gains, positive edge                            |
| `negative`                       | `#b91c1c`                           | `#f87171`             | losses, negative edge                           |
| `info` / `info-foreground`       | `#eff6ff` / `#1e40af`               | `#0c1a33` / `#93c5fd` | info banner                                     |
| `warning` / `warning-foreground` | `#fffbeb` / `#92400e`               | `#271a06` / `#fcd34d` | synthetic banner, live badge, overfit warning   |
| `danger` / `danger-foreground`   | `#fef2f2` / `#991b1b`               | `#2a0c0c` / `#fca5a5` | error states                                    |
| `chart-equity`                   | `#1d4ed8`                           | `#60a5fa`             | equity curve                                    |
| `chart-benchmark`                | `#52525b`                           | `#a1a1aa`             | benchmark curve                                 |
| `chart-oos`                      | `#b45309`                           | `#fbbf24`             | IS/OOS split line                               |

### Contrast (WCAG 2.2 AA)

Text needs 4.5:1, large text and control borders or focus rings need 3:1. Every pair below was computed from the values above.

| Pair                                       | Light                                              | Dark  |
| ------------------------------------------ | -------------------------------------------------- | ----- |
| foreground on background                   | 17.72                                              | 19.06 |
| muted foreground on background             | 7.73                                               | 7.76  |
| muted foreground on muted                  | 7.03                                               | 6.91  |
| muted foreground on card                   | 7.73                                               | 7.47  |
| foreground on accent (hover, best IS cell) | 16.28                                              | 14.08 |
| primary on accent (link hover)             | 6.16                                               | 5.78  |
| muted foreground on accent                 | 7.10                                               | 5.73  |
| primary on background (links)              | 6.70                                               | 7.83  |
| primary foreground on primary              | 6.70                                               | 7.83  |
| destructive foreground on destructive      | 6.47                                               | 7.19  |
| destructive on background (error text)     | 6.47                                               | 7.19  |
| positive on background                     | 5.02                                               | 11.42 |
| negative on background                     | 6.47                                               | 7.19  |
| positive on accent (best IS cell)          | 4.61                                               | 8.43  |
| negative on accent (best IS cell)          | 5.95                                               | 5.31  |
| info foreground on info                    | 8.01                                               | 9.61  |
| warning foreground on warning              | 6.84                                               | 11.78 |
| danger foreground on danger                | 7.60                                               | 9.57  |
| input border on background                 | 4.83                                               | 4.12  |
| input border on card                       | 4.83                                               | 3.96  |
| ring on background                         | 5.17                                               | 7.83  |
| chart OOS line on background               | 5.02                                               | 11.92 |
| chart equity and benchmark lines           | same as primary and muted foreground on background |       |

If you change a token, recompute its pairs and update this table in the same change.

## Typography

- **Fonts**: Geist Sans for text, Geist Mono for tickers and the JSON panel, both already loaded by `next/font` in `src/app/layout.tsx`. Remove the `font-family: Arial` rule from `globals.css` and set `font-sans` once on `html`.
- **Numbers**: every numeric cell and value uses `tabular-nums` so columns line up.
- **Scale** (Tailwind defaults): page title `text-2xl font-semibold`, section title `text-lg font-semibold`, body and table text `text-sm` (14 px), captions and hints `text-xs` (12 px, muted foreground only for non essential text).
- **Inputs** use `text-base` (16 px) below the `sm` breakpoint and `text-sm` from `sm` up, so phones do not zoom on focus.

## Spacing, radius, elevation

- Tailwind's 4 px spacing scale. Sections are separated by `gap-8`, controls in a row by `gap-2` or `gap-3`.
- Radius: one token, `--radius: 0.5rem`; controls use `rounded-md`, panels `rounded-lg`.
- Elevation: borders, not shadows. Only popovers and menus get `shadow-md`.

## Layout

- App shell: header, banner slot, main, footer. Main is `max-w-7xl` (1280 px; Tailwind v4 has no `max-w-screen-*`), centred, with `px-4` on phones and `px-6` from `md`.
- Mobile first. Below `sm` (640 px) every form row stacks into one column. Flex and grid children get `min-w-0`, and banner text wraps, so nothing pushes the page wide.
- Layouts must hold at 375 px (U-6) and at 320 px (WCAG reflow).
- Controls are at least 32 px tall (`sm`), default 36 px.
- The page never scrolls sideways. Wide tables scroll inside their own container.
- Breakpoints are the Tailwind defaults (`sm` 640, `md` 768, `lg` 1024, `xl` 1280).

## Focus, motion, icons

- Focus: one global rule, `:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }`. Remove the preset's `focus-visible:ring-*` classes (a 50% ring fails 3:1 and vanishes in Windows forced colours). Never remove the outline.
- Motion: fades and colour changes of 150 ms at most. A global rule under `prefers-reduced-motion: reduce` cuts every animation and transition to near zero; a still spinner is fine because text always carries the meaning.
- Icons: the icon set the shadcn preset installs (lucide), 16 px in controls and banners, always beside text or with an `aria-label`.

## Components

shadcn/ui, preset `base-nova` (Base UI primitives, nova style), copied into `src/components/ui/`. Shared app components that compose them live in `src/components/`. Generated files are edited to use tokens: replace the preset's `dark:bg-input/30` control fill with `bg-transparent` (the `input` token is a border colour), and make the destructive button a solid `destructive` fill with `destructive-foreground` text. The full inventory, behaviour, and acceptance criteria are in spec 0003. The `/ui` gallery page shows every component in every state.

## Copy

- Plain words, sentence case for headings and buttons ("Run backtest", not "Run Backtest").
- Missing numbers show `n/a`, never blank, `NaN`, or `0`.
- Dates show as `YYYY-MM-DD`, exactly as the API sends them (`formatDate` passes them through).
- Negative numbers use the ASCII minus; a value that rounds to zero shows no sign.
- Fixed copy decided elsewhere stays word for word: the synthetic banner (U-1), the warm up notice (U-5), the procedure note (U-8), the overfit warning (U-4).
