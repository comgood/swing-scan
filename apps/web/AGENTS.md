<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Conventions

- FE lane owns `apps/web/**`; API types come only from `@swing-scan/api-client`, mocks from `contracts/mocks/`.
- Folder by feature: `src/features/<name>/`. Static export only (`output: "export"`), no server routes.
- WCAG AA, keyboard usable, layouts hold at 375 px (U-6). Map 422 errors to their fields (U-7).
- Commands: `make dev-web`, `pnpm --filter web lint`, `pnpm --filter web typecheck`.
