# ADR 0001: Stack for v2 frontend rebuild

Status: **Accepted** (2026-04-30, Phase 0.7 of v2 rebuild)
Supersedes: nothing
Related: [`0002-auth.md`](0002-auth.md), [`0003-state-schema.md`](0003-state-schema.md), [`backend-requirements.md`](../../.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md), the approved plan at [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md)

## Context

The current site is a 66 kB single-file vanilla `index.html` with hand-rolled JS rendering, served by a thin Cloudflare Worker that proxies `data.json` and dispatches to GitHub Actions on Place clicks. It is deployable but unmaintainable: state lives in localStorage, there are no types, no component boundaries, no test surface, and it has accumulated 8 em-dashes in user-facing strings (which the universal rule on em-dashes will now flag on every edit).

The v2 rebuild adds real Google authentication and cross-device state. That work cannot reasonably ship inside a single-file vanilla HTML page. We need a real frontend framework, a real API layer, and a real type system shared between them.

This ADR pins the stack.

## Decision

### Frontend: Vite + React + TypeScript

- **Vite** for the dev server and build. Fast HMR, zero config beyond what `npm create vite` produces, and Cloudflare ships an official `@cloudflare/vite-plugin` that wires Vite into `wrangler dev` so the same command serves both the frontend and the worker locally.
- **React 18 (or 19 if stable by Phase 1)** with strict TypeScript. No `any` in app code.
- **TanStack Query** for server state. Fetches `/api/me`, `/api/picks`, `/api/bankroll`, `/api/state` and caches them with refetch-on-focus. Mutations for the POST endpoints with optimistic updates where useful.
- **Hand-rolled CSS** (no MUI, no Tailwind, no UI library) until we have a concrete reason. The current site already has a working visual language (sticky header, gold accent, Inter font, transaction-row layout) and we keep what works.
- **No router for v1 of v2.** Five tabs are tracked by a single `useState`. If we need real routing later we add `react-router` or TanStack Router.

### API layer: Hono on Cloudflare Workers

- **Hono** for the worker because it gives us typed routes, middleware composition (auth check, request validation), and tiny bundle size. It is Cloudflare-native and works with the same `wrangler dev` loop.
- **Zod** for request and response validation. Schemas live in `shared/schemas.ts` so the worker and the React app validate against the same definitions.
- **Single worker file per concern.** `worker/index.ts` mounts routes from `worker/routes/*.ts`. Middleware in `worker/middleware/*.ts`. Pure helpers (KV reads, GitHub dispatch) in `worker/lib/*.ts`. Folder shape was scaffolded in Phase 0.4.

### Repo layout

```
~/Betting Skill/                    # repo root, branch rebuild/v2-frontend
├── frontend/                       # Vite scaffold lands here in Phase 1
│   ├── src/
│   ├── public/
│   └── package.json
├── worker/
│   ├── index.ts                    # Hono app, mounts routes
│   ├── routes/                     # one file per endpoint group
│   ├── middleware/
│   └── lib/
├── shared/
│   ├── schemas.ts                  # Zod schemas
│   └── types.ts                    # TS types
├── docs/adr/                       # this file lives here
├── scripts/                        # Python model, untouched
├── data.json                       # Python output, untouched
├── bankroll.json                   # Python output, untouched
├── pick_history.json               # Python output, untouched
├── index.html                      # current single-file frontend, kept until cutover
├── wrangler.jsonc
└── ...
```

### Cohabitation during the rebuild

The Worker routes between old and new during the rebuild:
- `/v2/*` and `/api/*` go to the v2 app (Vite build output + Hono)
- everything else goes to the existing `index.html` static asset

At cutover, the old `index.html` moves to `legacy/index.html` and is reachable at `/legacy` for one week as a fallback, then removed.

## Consequences

### What we gain
- **Type safety end to end.** Shared Zod schemas mean a contract change in `shared/schemas.ts` breaks the worker AND the frontend at compile time. No more discovering a renamed field at render.
- **Real component boundaries.** `PicksTab`, `PendingTab`, `BalanceCard`, `PickRow` become independently reasonable units instead of paragraphs of string concatenation in `renderPicks()`.
- **Test surface.** Components testable with Vitest + Testing Library; route handlers testable with `unstable_dev` from wrangler.
- **Fast dev loop.** Vite HMR + `@cloudflare/vite-plugin` gives sub-second feedback for both frontend and worker edits.
- **Smaller deploys.** Vite tree-shakes unused code. The 66 kB single-file frontend has dead code paths from the abandoned-rebuild migration; v2 ships only what's used.

### What we accept
- **Build step.** The current site has none. The v2 site has Vite. Tradeoff is worth it for the type/component wins, but `wrangler deploy` now requires `npm run build` first. Captured in `package.json` scripts so it is one command.
- **Node version dependency.** Vite needs Node 18+. Captured in `.nvmrc`.
- **More moving parts.** Worker plus frontend plus shared types plus build pipeline. Mitigated by `@cloudflare/vite-plugin` collapsing the dev loop into one `wrangler dev`.

## Alternatives considered

### Next.js
- Pros: ecosystem, App Router, RSC, well-documented Vercel deploys.
- Cons: heavy. Cloudflare Workers via `@cloudflare/next-on-pages` works but adds an extra abstraction layer over our already simple worker. We do not need RSC, we do not need server components, we do not need Vercel. Hono + Vite is leaner for this scope.
- Decision: not chosen. Reconsider only if the app grows to need multi-page server-rendered marketing surface, which is not on the roadmap.

### Remix
- Pros: nested routing, loaders/actions for data flow.
- Cons: same weight critique as Next.js. Cloudflare integration is workable but not as native as Hono.
- Decision: not chosen.

### SvelteKit
- Pros: smaller runtime, excellent Cloudflare adapter.
- Cons: Max prefers React. The skill folder under `~/.claude/skills/` contains React-specific best-practices skills (`react-dev`, `react-useeffect`); none for Svelte. Switching frameworks loses that compounding leverage.
- Decision: not chosen.

### Plain HTML/JS (keep the current shape)
- Pros: zero build, zero dependencies.
- Cons: cannot ship real auth + cross-device sync without component boundaries and shared types. The current code has already shown what hand-rolled string templating costs (lessons.md 2026-03-21 and 2026-04-19 both have entries about template-literal bugs in `index.html` that made it to prod).
- Decision: explicitly rejected.

### MUI or another UI library
- Pros: ready-made components.
- Cons: bundle size, opinionated styling, slower to customize than to hand-roll for a small app. The current site's CSS works.
- Decision: not chosen for v1 of v2. Reconsider per-component if we hit something hard to build (date picker, modal stack, etc.).

### Tailwind
- Pros: utility classes, fast iteration.
- Cons: another tool. Hand-rolled CSS is fine for a small surface and matches the current visual language.
- Decision: not chosen for v1 of v2. Reconsider if the CSS surface grows past where hand-rolled scales.

## Implementation notes (for Phase 1)

- Scaffold: `npm create vite@latest frontend -- --template react-ts` from repo root.
- Add Cloudflare plugin: `npm install -D @cloudflare/vite-plugin` and configure `vite.config.ts` to use it.
- Worker conversion: rewrite the existing `worker/index.js` as `worker/index.ts` mounting Hono.
- Shared types live at the repo root in `shared/`, imported by both `frontend/` and `worker/`.
- Wrangler config: `main` points at the worker entry, `assets.directory` points at `frontend/dist` (post-build) for the v2 surface, and the legacy `index.html` is served via a worker route for non-v2 paths until cutover.
