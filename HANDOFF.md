# DK Edge Finder v2 Rebuild Handoff

Running session-handoff doc. Newest section on top. **Update this file as you work, not only at session end.** Update after every milestone, before any risky push or merge, and any time the context window fills up. A crash mid-session loses everything since the last write.

## Universal rules to read FIRST (every fresh session)

Before any project-specific work, the next thread must load these:

1. `~/.claude/CLAUDE.md` (Max's universal rules: no em-dashes, ask one prompted question at a time via `AskUserQuestion`, trust the user's eyes, do not wrap guesses in the cover of certainty, do not be lazy on visual bug investigations).
2. The approved plan at [`/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md).
3. This HANDOFF.md in full (you are reading it).
4. `dk-edge-finder/tasks/lessons.md` for model lessons (existing file with full history).
5. `lessons.md` at repo root for rebuild-specific lessons (currently empty template; populate as you work).

## What you are inheriting (2026-05-01, Phase 1 closed code-side, Phase 2 in progress)

A live Cloudflare Workers site at https://dk-edge-finder.max-sheahan.workers.dev/ that serves a 66 kB single-file vanilla `index.html` backed by a Python edge-finder model on GitHub Actions cron. **Phase 0 is closed. Phase 1 is closed code-side; step 8 (Access dashboard config) is still pending and is Max's hands-on click-through.** Phase 2 (quality gate) is in progress: vitest harness shipped, picks normalizer + read-route tests + non-dispatch write-route tests all green (65 tests total). Dispatch-touching routes (`/api/state/sync-queue/retry`, `/api/place-bet`) need a fetch-injection seam in `worker/lib/dispatch.ts` before they can be unit-tested without a real GitHub call; that's the only remaining Phase 2 code work.

Step 8 detection at the start of session 4 (2026-05-01) via `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/api/me` returned `HTTP/2 200` with `content-type: text/html` and no `cf-access-*` headers, meaning Access is not yet intercepting requests on the live URL. Max chose to start Phase 2 now using the dev-mock header path; the live-smoke step (Phase 2.3) is deferred until step 8 lands.

Phase 1 step status (sequence per the bottom of session 2 below):
- [x] **Step 1**: Vite + React + TS scaffolded into `frontend/` (Vite 8, React 19, TS 6).
- [x] **Step 2**: `@cloudflare/vite-plugin` v1.35.0 installed and wired.
- [x] **Step 3**: `worker/index.js` rewritten as `worker/index.ts` mounting Hono 4.12.16. Layout restructured: `package.json`, `vite.config.ts`, `tsconfig*.json`, `eslint.config.js` moved from `frontend/` up to the repo root. Vite uses `root: 'frontend'`. ADR 0001 amended to match.
- [x] **Step 4**: `EDGE_STATE` KV namespace created (id `7dca36afc97d4d86bebed2e2948d6e83`), bound in `wrangler.jsonc`, types regenerated. Skipped a separate preview namespace; the Cloudflare Vite plugin uses miniflare for local dev.
- [x] **Step 5**: `worker/middleware/auth.ts` shipped (per ADR 0002). Defined but not yet mounted in `worker/index.ts` at the time. Mount landed in step 6.
- [x] **Step 6**: Zod schemas in `shared/schemas.ts`, type re-exports in `shared/types.ts`, helper libs in `worker/lib/{picks,bankroll,state}.ts`, four read routes in `worker/routes/{me,picks,bankroll,state}.ts`. `requireAuth` mounted on each v2 route (`app.use('*', requireAuth)`). Legacy `/api/health` and `/api/place-bets` mount FIRST in `worker/index.ts` so they stay public until Access goes live in step 8. `npx tsc -b` clean.
- [x] **Step 7**: Write routes shipped. Request schemas added to `shared/schemas.ts` (`PlacementCreateRequestSchema`, `ManualBetCreateRequestSchema`, `SyncQueueRetryRequestSchema`, `BalanceOverrideRequestSchema`, `PlaceBetRequestSchema`, `PlaceBetResponseSchema`). State helpers extended (`removePlacement`, `removeManualBet`, `getBalanceOverride`, `upsertBalanceOverride`, `findSyncQueueEntry`); `upsertSyncQueueEntry` re-keyed from `idempotency_key` to `key` so retry attempts update one row instead of creating new ones. `worker/lib/dispatch.ts` added (GitHub `repository_dispatch` plus 24h-TTL idempotency cache via `dispatch:<email>:<idempotency_key>` KV keys). Five new routes: `state-placements` (POST + DELETE :key), `state-manual-bets` (POST + DELETE :id), `state-sync-queue` (POST /retry), `balance-override` (POST), `place-bet` (POST, singular, idempotent). Legacy `place-bets` (plural, no idempotency) untouched. `npx tsc -b` clean. A small Hono mount-order smoke (one-shot, deleted) confirmed `/api/state/placements` routes to the write subapp without firing stateApp middleware.
- [ ] **Step 8**: Cloudflare Access policy in dashboard. **Runbook drafted** at [`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md). Awaiting Max's manual dashboard click-through. Recommended scope: `/api/*` initially, expand to `/*` after step 9 cutover. Worker code does NOT need any further changes for step 8.
- [x] **Step 9**: EMFILE fix landed. Root cause was NOT the asset upload size (`.assetsignore` does not affect the dev watcher); it was the dev watcher walking the entire repo because `wrangler.jsonc` had `assets.directory: "."`. Fixed by narrowing `assets.directory` to `public/` and creating three symlinks inside it pointing one level up at the actual served files (`index.html`, `data.json`, `bankroll.json`). The Python cron still writes to repo root unchanged; symlinks expose the writes transparently. macOS launchd's default per-process file-descriptor cap is 256 (visible via `launchctl limit maxfiles`), which is why the wide watch tree exhausted descriptors despite `ulimit -n` reporting 1M+. `.assetsignore` was added too as defense-in-depth (default-deny, allowlists only the three served files), which has the side benefit of stopping the public site from serving `pick_history.json` (535 KB of model calibration data, no purpose on the public URL). Live `wrangler dev` smoke now passes for all 9 v2 routes (read + write); see commit message for the round-trip details.

Branch `rebuild/v2-frontend` is ahead of origin (commits will increment after step 8/9 commits), not yet pushed. Live site unaffected.

---

## 2026-05-01 session 4 (IN PROGRESS, Phase 2 quality gate)

### Goal
Land Phase 2 (vitest harness for the worker; route tests via direct `app.fetch(new Request(...))`; live smoke against the deployed URL once Access is configured). Step 8 (Access dashboard) is still pending; Max chose to start Phase 2 now using the dev-mock header path and defer the live smoke until step 8 lands.

### Pre-flight
- `git stash list` empty before any work. Skipped `git pull --rebase` because origin is behind (branch is 14 commits ahead, nothing to pull).
- Step 8 detection via `curl -sI https://dk-edge-finder.max-sheahan.workers.dev/api/me` returned `HTTP/2 200` with `content-type: text/html` and no `cf-access-*` headers. Two signals folded into one response: (a) Access is not yet intercepting requests on the live URL (no 302 to `*.cloudflareaccess.com`), and (b) the new worker code is still unpushed (the deployed legacy worker has no `/api/me` route, so the request fell through to the assets binding and served `index.html`).

### Phase 2 step 1 (vitest harness): what shipped

**Tooling.**
- `npm install -D vitest` brought in `vitest@4.1.5` (Node 24 friendly).
- Added `"test": "vitest run"` and `"test:watch": "vitest"` scripts to `package.json`.
- Wrote standalone `vitest.config.ts` at the repo root with `environment: 'node'` and `include: ['worker/**/*.test.ts', 'shared/**/*.test.ts']`. Standalone (rather than inheriting `vite.config.ts`) so vitest does NOT load the Cloudflare Vite plugin, which is meant for `wrangler dev` and would noisily try to read `wrangler.jsonc` during test discovery.

**Picks normalizer tests (`worker/lib/picks.test.ts`).** 31 tests across nine `describe` blocks. The unit under test is `getPicksResponse(env)` (and `loadDataJson` / `getLatestScanDate` as supporting exports). Each test builds a fake `Env` with a hand-rolled `ASSETS.fetch` shim that returns a `Response` with a configurable `data.json` body and an optional `Last-Modified` header. Coverage:

- **Em-dash strip**: `scan_subtitle`, all `Pick` string fields (event/notes/sources), `no_edge_games[]` strings, `best_bet.title|desc`. Asserts both the stripped output AND that `JSON.stringify(...)` of the result contains no `—`.
- **Percent-string coercion**: `"35.7%"` → `35.7` for `implied`/`model`/`edge`. Numeric pass-through. Fallback to `0` for `null`/`undefined`/non-numeric strings. The `implied_prob` and `model_prob` fallback keys (legacy emit shape) are also covered.
- **Dollars-string coercion**: `"$11.41"` → `11.41` for `wager`. The `bet` fallback key (legacy shape) is covered. Numeric pass-through. Embedded-comma strings (`"$1,234.56"`) parse correctly. Missing wager defaults to `0`.
- **Odds string coercion**: passthrough of pre-formatted American strings (`"-110"`); numeric `165` → `"+165"`; numeric `-110` → `"-110"`.
- **Missing-field defaults**: a fully-empty pick object (`{}`) normalizes into a Pick that satisfies the schema with safe defaults across every field. Fallback `rank` from array index is verified. `type` falls back to `'game'` for unknown values; preserves `'prop'` when set. Top-level optional fields (subtitle/games_analyzed/best_bet/picks/no_edge_games) fall back when the model omits them.
- **scan_age_seconds derivation**: with `Last-Modified` 10 minutes ago → ~600 (asserted in a 599-601 window for clock skew). With absent header → `null`. With unparseable header → `null`. With future `Last-Modified` → clamped to `0`.
- **Empty-picks case**: today's actual zero-edges shape (`picks: []`, `no_edge_games: [...]`) round-trips correctly with em-dash stripped from `scan_subtitle`.
- **Schema validation**: a malformed `scan_date` (e.g. `"not-a-date"`) causes `PicksResponseSchema.parse(...)` to throw, which the test asserts via `rejects.toThrow()`.
- **`loadDataJson` / `getLatestScanDate`**: success path returns parsed data + `Last-Modified` Date; non-OK ASSETS response throws `data.json fetch failed: 404`; missing or non-string scan_date returns `''` from `getLatestScanDate`.

One test failed on first run (`top-level missing scan fields fall back to safe defaults`) because passing `{}` as data.json defaults `scan_date` to `''`, which fails Zod's ISO-date validator. The Python model always emits `scan_date`; a missing one is a real failure mode (not a graceful default), so the test was retitled and now provides a minimal valid `scan_date`. The schema-validation block keeps a separate negative case for the malformed-date scenario.

### Phase 2 step 2 (route tests via app.fetch): what shipped

**`worker/index.test.ts`** — 17 tests that drive the assembled root `app` (from `worker/index.ts`) via `app.fetch(new Request(...), env)`. Same pattern as the one-shot mount-order smoke from Phase 1 step 7, codified.

Mock env helpers in the file:
- `makeAssets(cfg)` returns an `ASSETS` shim that responds to `/data.json` and `/bankroll.json` with caller-provided fixtures and an optional `Last-Modified`. Anything else → 404.
- `makeKv()` returns a `Map<string, string>`-backed `EDGE_STATE` shim with `get`/`put`/`delete`/`list`. Pre-seeded via direct `env.EDGE_STATE.put(...)` calls in tests that need existing state.
- `makeEnv({ dataJson?, bankrollJson?, dataLastModified? })` composes both bindings + a placeholder `GITHUB_TOKEN`.

Coverage:
- **Auth gating** (5 tests): every v2 read route returns 401 without `cf-access-authenticated-user-email`. The middleware lowercases the email; verified by passing `Max.Sheahan@iCloud.com` and asserting `/api/me` returns `email: "max.sheahan@icloud.com"`.
- **`GET /api/health`** (1 test): public, returns `{ ok: true, time: "2026-..." }` without auth.
- **`GET /api/me`** (4 tests): happy path returns the lowercased email. JWT picture extraction works for both top-level `picture` and `custom.picture` claim shapes (test builds a fake JWT with hand-rolled base64url helper using `btoa` to keep `@types/node` out of the worker tsconfig). Malformed JWT yields `picture_url: null` rather than throwing.
- **`GET /api/picks`** (2 tests): normalized payload returned, em-dash stripped from `scan_subtitle`, schema-validated. Asset 404 on `data.json` propagates as a 500 (Hono's default error handler).
- **`GET /api/bankroll`** (2 tests): file values flow through when no KV override exists. Per-user override pre-seeded via `EDGE_STATE.put('balance_override:<email>', ...)` overrides `available` AND populates the `balance_override` envelope.
- **`GET /api/state`** (2 tests): empty KV returns empty arrays + `null updated_at` + the current `scan_date`. Pre-seeded record at `state:<email>:<scan_date>` round-trips through the merged response.
- **Mount-order regression** (1 test): `POST /api/state/placements` with an empty body returns 400 (Zod validation error from the placements subapp), NOT 404 (which would mean the broader `/api/state` router swallowed the path). This codifies the smoke from step 7.

**Initial run.** All 48 tests passed first try. `npx tsc -b` flagged one issue: my JWT helper used `Buffer.from(...).toString('base64')`, but the worker tsconfig doesn't include `@types/node` (correct; the worker shouldn't reach for Node APIs). Switched to `btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')` which works in both the Workers runtime and Node. `tsc -b` and `npm test` both clean afterward.

### Phase 2 step 2 extension (write-route tests, non-dispatch): what shipped

After the first commit pair landed, extended `worker/index.test.ts` with 17 more tests (65 total) covering the write routes that only touch KV. The dispatch-touching routes (`POST /api/state/sync-queue/retry`, `POST /api/place-bet`) are deliberately deferred: they need a fetch-injection seam in `worker/lib/dispatch.ts` before they can be unit-tested without a real GitHub `repository_dispatch` call. A comment in the test file flags the deferral so a future thread doesn't think coverage is just missing.

Coverage by route:

- **POST /api/state/placements** (5 tests): happy-path 201 with server-stamped `placed_at`, idempotency dedupe (same `idempotency_key` twice = one entry in the merged record), `dispatch_status` defaulting to `'ok'` when omitted from the body, 400 with Zod issues on bad body, 401 without auth header.
- **DELETE /api/state/placements/:key** (4 tests): 204 No Content on success with empty body, 404 when no state record exists at all, 404 when the key is not present in `placements[]`, URL-decoding of special chars (`|`, `%20`, `%40`) confirmed via a key like `NYY +1.5|NYY @ BOS`.
- **POST /api/state/manual-bets** (3 tests): 201 with server-assigned `id = idempotency_key` and `outcome: 'pending'`, idempotency dedupe, 400 on bad body.
- **DELETE /api/state/manual-bets/:id** (2 tests): 204 on success, 404 on missing id.
- **POST /api/balance-override** (3 tests): 200 with persisted record, subsequent POST overwrites the previous override (upsert semantics), `/api/bankroll` reflects the override after the POST (cross-route side-effect verified), 400 on bad body.

All 65 tests passed first run. `npx tsc -b` clean.

### Where this leaves us at end of session
- 65 tests passing across 2 files (`worker/lib/picks.test.ts` 31, `worker/index.test.ts` 34).
- `npx tsc -b` clean.
- Phase 2 step 3 (live smoke) blocked on step 8 (Access dashboard).
- Phase 2 internal coverage gap: dispatch-touching write routes (`POST /api/state/sync-queue/retry`, `POST /api/place-bet`) deferred until a fetch-injection seam lands in `worker/lib/dispatch.ts`.
- Three commits this session: `4175694` (vitest + picks + read routes), `dffc87b` (HANDOFF update), then the next pair lands when the write-route tests + this HANDOFF update commit.

### What's next (continue here on resume)

1. Step 8 (Access dashboard click-through) when Max is ready. Runbook at [`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md).
2. Phase 2.3 live smoke once step 8 is live.
3. Optional follow-up to close the Phase 2 internal gap: refactor `worker/lib/dispatch.ts` to accept an injectable `fetch` (or swap to `vi.stubGlobal('fetch', ...)`), then add tests for `POST /api/state/sync-queue/retry` and `POST /api/place-bet` covering: idempotency cache hits return the cached result without re-dispatching, dispatch failure returns 502, dispatch success returns 202, sync-queue retry updates `attempt_count` and `last_error`. Not blocking Phase 3 cutover, but worth doing before retry logic lands in the v2 frontend.

### If you just have one minute, do this
Run `cd ~/Betting\ Skill && npm test` to confirm 65/65 pass. Then `npx tsc -b` to confirm types are clean. If both pass, the next decision is step 8 (Max's dashboard click-through) or the dispatch-injection refactor.

---

## 2026-04-30 session 3 (PAUSED, Phase 1 implementation)

### Goal
Land Phase 1: scaffold the Vite app, wire Hono in TypeScript, create the KV namespace, ship the auth middleware and route handlers, configure Cloudflare Access. Live site stays untouched throughout.

### What shipped this session so far

**Phase 1 step 1 (scaffold).** Ran `npx -y create-vite@latest frontend --template react-ts` from repo root. Output: `frontend/` with React 19.2.5, Vite 8.0.10, TypeScript 6.0.2, ESLint 10. `frontend/.gitignore` covers `node_modules/` and `dist/`. The repo's root `.gitignore` also covers them; double-coverage is fine.

**Phase 1 step 2 (Cloudflare plugin + vite.config).** `npm install` then `npm install -D @cloudflare/vite-plugin` in `frontend/` (190 packages total, 0 vulns). Installed version `@cloudflare/vite-plugin@1.35.0`. The plugin exports a named `cloudflare(pluginConfig?: PluginConfig): vite.Plugin[]`; `PluginConfig` extends `EntryWorkerConfig` which includes `configPath?: string`.

`frontend/vite.config.ts` final shape:
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cloudflare } from '@cloudflare/vite-plugin'

export default defineConfig({
  plugins: [
    react(),
    cloudflare({ configPath: '../wrangler.jsonc' }),
  ],
})
```

`tsc --noEmit` clean against both `tsconfig.app.json` and `tsconfig.node.json`. Did NOT yet attempt `npm run dev` because step 9 (`.assetsignore` + `assets.directory` fix) still needs to land before `wrangler dev` can start without EMFILE.

**Decisions locked in this session (carried forward into HANDOFF):**

1. **Single `package.json`, located at `frontend/`.** All deps (frontend AND worker) live in `frontend/package.json`. Per ADR 0001's repo-layout block. The cloudflare-vite-plugin will bundle the worker via Vite using the same node_modules tree, so `hono` and `zod` (added in step 3) get installed there too. No root `package.json`, no workspaces.
2. **wrangler.jsonc stays at the repo root.** Vite plugin reads it from `../wrangler.jsonc`. The worker entry path inside it (`main: "worker/index.js"` today, will become `worker/index.ts` in step 3) resolves relative to wrangler.jsonc's own directory (root), so existing path stays correct.

### Open questions surfaced this session (to address before step 7)

- **Legacy `/api/place-bets` (plural) vs new `/api/place-bet` (singular).** The existing Worker at `worker/index.js` exposes `/api/place-bets`. The locked contract calls for `/api/place-bet` with idempotency. Plan: keep both working through cohabitation. Old `index.html` keeps hitting `/api/place-bets`; new v2 frontend hits `/api/place-bet`. After cutover, deprecate the plural. Worth confirming with Max before writing the singular endpoint in step 7.

### Phase 1 step 3 (worker rewrite + layout shift): what shipped

**Layout shift (deviation from ADR 0001 as originally written).** ADR 0001's repo-layout block placed `package.json` inside `frontend/`. When I tried to typecheck `worker/*.ts` with imports of `hono` and `zod`, TypeScript could not resolve them: `worker/` is a sibling of `frontend/`, and the standard module resolution (even in `bundler` mode) walks up from each file looking for `node_modules`. From `worker/index.ts`, walking up never reaches `frontend/node_modules`. Two fix options were considered (paths mapping in `tsconfig.worker.json` with deprecated TS 6 `baseUrl`, vs moving `package.json` to the repo root). Asked Max via `AskUserQuestion`; chose the canonical CF Workers + Vite layout: package.json at the repo root.

**Files moved from `frontend/` to repo root:**
- `package.json`
- `package-lock.json`
- `vite.config.ts`
- `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `tsconfig.worker.json`
- `eslint.config.js`

**Files left in `frontend/`:** `src/`, `public/`, `index.html` (Vite's HTML entry), `README.md`. `frontend/node_modules` deleted; `node_modules` reinstalled at the repo root via `npm install`.

**Config updates that paired with the move:**
- `vite.config.ts`: `root: 'frontend'` so Vite finds `frontend/index.html`. `cloudflare()` plugin no longer needs `configPath` since `wrangler.jsonc` is at the same level.
- `tsconfig.app.json`: `include` changed from `["src"]` to `["frontend/src"]`.
- `tsconfig.worker.json`: paths in `include` no longer prefixed with `../`. Dropped the `baseUrl` + `paths` workaround that I had attempted before the layout shift (deprecated in TS 6).
- `eslint.config.js`: `globalIgnores` extended to `['dist', 'frontend/dist', 'node_modules', '.wrangler']`.

**Worker rewrite (TS + Hono).** Under `worker/`:
- `worker/env.ts`: `Env extends CloudflareBindings` with `GITHUB_TOKEN: string` (the secret is not in wrangler.jsonc, so `wrangler types` does not generate it).
- `worker/index.ts`: `Hono<{ Bindings: Env }>` app that mounts `app.route('/api/health', healthApp)`, `app.route('/api/place-bets', placeBetsLegacyApp)`, and falls through with `app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))`.
- `worker/routes/health.ts`: tiny health endpoint, identical behavior to the JS original.
- `worker/routes/place-bets-legacy.ts`: 1:1 port of the existing JS handler. CORS allowlist, origin check, body parse, `normalizePicks`, GitHub `repository_dispatch`. Live behavior preserved.
- `wrangler.jsonc`: `main` updated from `worker/index.js` to `worker/index.ts`.
- `worker/index.js` and `worker/routes/.gitkeep` deleted.
- `worker-configuration.d.ts` regenerated via `npx wrangler types --env-interface CloudflareBindings`. Lives at the repo root, ~500 KB; committed for editor type support. Re-run after any wrangler.jsonc binding change (the wrangler CLI prints a reminder).

`npx tsc -b` from the repo root passes clean across all three project references (app, node, worker).

### Decisions locked this session

1. **Single `package.json`, located at the repo root** (revises ADR 0001's layout). Matches the canonical CF Workers + Vite template.
2. **wrangler.jsonc stays at the repo root.** Now sibling to `vite.config.ts`, so the Cloudflare Vite plugin auto-detects it.
3. **Worker has its own tsconfig (`tsconfig.worker.json`).** Wires `worker/**/*.ts`, `shared/**/*.ts`, and the generated `worker-configuration.d.ts`. ESM module resolution mode `bundler`, no DOM lib, strict.
4. **Legacy `/api/place-bets` (plural) preserved verbatim** as a 1:1 TS port. The new `/api/place-bet` (singular, with idempotency) lands in step 7.

### Open questions surfaced this session (unchanged, still open for step 7)

- **Legacy `/api/place-bets` (plural) vs new `/api/place-bet` (singular).** Plan: keep both during cohabitation. Old `index.html` keeps hitting the plural path; new v2 frontend hits the singular path. After cutover, deprecate the plural. Worth confirming with Max before writing the singular endpoint in step 7.

### TODOs surfaced (non-blocking, address in later steps or polish pass)

- `eslint.config.js` applies `globals.browser` to `**/*.{ts,tsx}` including `worker/`. Worker code does not run in a browser. Split the rules into a frontend block (browser globals + react) and a worker block (no DOM). Polish item; not blocking.
- `worker-configuration.d.ts` is committed at ~500 KB. Common practice is to either commit it (as the canonical CF template does) or gitignore + regenerate via `predev`/`prebuild`. Currently committed. Revisit if it gets noisy.
- ESLint, Vitest, and full deploy scripts are not wired into `package.json` yet beyond the Vite scaffold defaults. Step 9 (cohabitation + EMFILE) is a natural place to add `deploy`, `types`, and worker-aware scripts.

### Phase 1 step 4 (KV namespace): what shipped

Ran `npx wrangler kv namespace create EDGE_STATE` from the repo root. Cloudflare returned namespace id `7dca36afc97d4d86bebed2e2948d6e83`. Wrangler offered to auto-edit `wrangler.jsonc` but in non-interactive mode defaulted to "no", so the binding was added by hand:

```jsonc
"kv_namespaces": [
  { "binding": "EDGE_STATE", "id": "7dca36afc97d4d86bebed2e2948d6e83" }
]
```

`npx wrangler types --env-interface CloudflareBindings` regenerated `worker-configuration.d.ts`. `Cloudflare.Env` now contains `EDGE_STATE: KVNamespace`, which `worker/env.ts`'s `Env extends CloudflareBindings` picks up automatically.

Skipped the separate `_PREVIEW` namespace. The Cloudflare Vite plugin runs miniflare for local dev and simulates KV in memory; a remote preview namespace is only needed if `wrangler dev --remote` against real Cloudflare KV becomes the workflow. Add later if so.

`npx tsc -b` clean.

### Phase 1 step 5 (auth middleware): what shipped

`worker/middleware/auth.ts`:
```ts
import { createMiddleware } from 'hono/factory'
import type { Env, Variables } from '../env'

export const requireAuth = createMiddleware<{
  Bindings: Env
  Variables: Variables
}>(async (c, next) => {
  const email = c.req.header('cf-access-authenticated-user-email')?.toLowerCase()
  if (!email) return c.text('Unauthorized', 401)
  c.set('email', email)
  await next()
})
```

`worker/env.ts` gains a `Variables` type export so consumers of `requireAuth` can construct a typed Hono app:
```ts
new Hono<{ Bindings: Env; Variables: Variables }>()
```

`worker/middleware/.gitkeep` removed.

**Not yet mounted in `worker/index.ts`.** Mounting on `/api/*` would 401 the legacy `/api/place-bets` path that the live `index.html` still calls (the live site does not yet route through Cloudflare Access, so it has no `cf-access-authenticated-user-email` header). Step 6 will mount `requireAuth` on each new v2 read route as it lands. Once Cloudflare Access is configured in step 8, the same header will populate for legacy traffic too, but until then the cohabitation worker has to keep legacy paths public.

### Phase 1 step 6 (read routes + shared schemas): what shipped

**`shared/schemas.ts`** — Zod 4 schemas for the locked contract. One block per concern:
- `PickSchema` (v2 normalized output), `NoEdgeGameSchema`, `BestBetSchema`, `PicksResponseSchema`.
- `LifetimeStatsSchema`, `BankrollResponseSchema`.
- `MeResponseSchema`.
- `PlacementSchema`, `SyncQueueEntrySchema`, `ManualBetSchema`, `StateRecordSchema`, `BalanceOverrideRecordSchema`, `StateResponseSchema`.

Schema choices grounded in the actual emit shape from `scripts/scan_edges.py:1968-1990`:
- Q6 normalization is opinionated. The Python model emits `implied: "35.7%"` (string with %) and `bet: "$11.41"` (formatted dollars). The schema requires `implied: number` and `wager: number`; the normalizer in `worker/lib/picks.ts` does the coercion. `event_short` and the empty `status`/`result` fields are dropped at the boundary.
- Em-dash strip is universal across every string the worker returns (per the contract's "Display contracts" section, which is a hard rule, not a suggestion).
- Used Zod 4's top-level `z.iso.date()` and `z.iso.datetime({ offset: true })` for ISO date/timestamp validation; `z.string().email()` is deprecated in v4.

**`shared/types.ts`** — `import type { z } from 'zod'` plus `import type { ... } from './schemas'`, then `type Pick = z.infer<typeof PickSchema>` etc. for every schema. Worker and (future) frontend share these types from one source.

**`worker/lib/picks.ts`** — `loadDataJson(env)`, `getLatestScanDate(env)`, `getPicksResponse(env)`. Reads `/data.json` via `c.env.ASSETS.fetch(new Request('https://assets.local/data.json'))`. `scan_age_seconds` is derived from the response's `Last-Modified` header (null if absent). Coercion helpers: `coerceNumberPercent` (strips `%`), `coerceNumberDollars` (strips `$`), `coerceOddsString` (number → American format string with `+`/`-` prefix), `stripEmDash` (replaces `—` with `-` everywhere). Final `PicksResponseSchema.parse()` validates the normalized shape before returning, so a model regression that breaks the contract surfaces as a 500 with a Zod error rather than malformed JSON.

**`worker/lib/bankroll.ts`** — `getBankrollResponse(env, email)`. Reads `/bankroll.json` via ASSETS in parallel with the per-user `balance_override:<email>` KV record. If the user has a KV override, that wins for both `available` and the `balance_override` envelope; otherwise `available` falls back to `current_bankroll` from the file and `balance_override` is `null`. Lifetime stats always come from the file.

**`worker/lib/state.ts`** — `readState(env, email, scan_date)`, `writeState(env, record)`, `appendPlacement(env, email, scan_date, p)`, `appendManualBet(env, email, scan_date, b)`, `upsertSyncQueueEntry(env, email, scan_date, entry)`. Append-merge semantics with idempotency-key dedupe per ADR 0003. The append helpers will land in active use during step 7 (write routes); they are written now so the lib layer stays cohesive.

**`worker/routes/me.ts`** — JWT decode of `cf-access-jwt-assertion` (no signature verification; Access already guards the path per ADR 0002 Section "What we accept"). Extracts `picture` claim if present, falls back to `null`. Returns `{ email, picture_url }`.

**`worker/routes/picks.ts`** — thin: calls `getPicksResponse(c.env)`, returns it.

**`worker/routes/bankroll.ts`** — thin: calls `getBankrollResponse(c.env, c.get('email'))`, returns it.

**`worker/routes/state.ts`** — reads latest `scan_date` from `data.json`, then `readState(env, email, scan_date)`. If null, returns empty arrays + `updated_at: null` (per the open-question default in `backend-requirements.md`). Includes `scan_date` in the response so the frontend can display which scan the state belongs to.

**Mount order in `worker/index.ts`** — legacy `/api/health` and `/api/place-bets` mount FIRST so the live `index.html` keeps working without a Cloudflare Access header. v2 read routes mount after; each route's own `app.use('*', requireAuth)` provides the 401 gate. Once Access goes live in step 8, the same header will populate for legacy traffic too and we can either tighten the legacy routes or leave them as the cohabitation fallback.

`npx tsc -b` clean. Manual `wrangler dev` smoke deferred to after step 9 (EMFILE).

### Decisions locked at the step 6 / step 7 handoff

- **Singular `/api/place-bet` vs plural `/api/place-bets`** — Max confirmed (2026-04-30, end of step 6): **both coexist during cohabitation.** Legacy plural stays wired for the live `index.html`. The new singular endpoint adds idempotency via a client-generated UUID in the request body. Plural deprecates after cutover (step 9 / Phase 3 territory).

### Phase 1 step 7 (write routes): what shipped

**Schemas (`shared/schemas.ts`).** Six new request/response shapes, all with `idempotency_key: z.string().min(1)` where applicable:

- `PlacementCreateRequestSchema { key, action, dispatch_status, idempotency_key }` — `dispatch_status` defaults to `'ok'` so the frontend can record skipped placements without specifying it. The frontend reports the dispatch outcome alongside the placement so the worker stays stateless about the place-bet flow.
- `ManualBetCreateRequestSchema { sport, event, pick, odds, wager, idempotency_key }` — server assigns `id = idempotency_key` so retries dedupe cleanly.
- `SyncQueueRetryRequestSchema { key, idempotency_key }` — `idempotency_key` is for THIS retry attempt's dispatch dedupe, not the original placement.
- `BalanceOverrideRequestSchema { amount, note }`.
- `PlaceBetRequestSchema { pick_indices: number[].min(1), idempotency_key }`.
- `PlaceBetResponseSchema { status: 'ok'|'failed', dispatch_id?, error? }` — `dispatch_id` echoes the idempotency_key so the client can correlate.

Re-exported as TS types in `shared/types.ts`.

**State lib (`worker/lib/state.ts`).** Extended:
- `removePlacement(env, email, scan_date, key)` and `removeManualBet(env, email, scan_date, id)` filter the array, write back, return `{ removed, record }`.
- `getBalanceOverride(env, email)` and `upsertBalanceOverride(env, email, amount, note)` operate on the `balance_override:<email>` KV key. `lib/bankroll.ts` was deduped to call `getBalanceOverride` instead of carrying its own copy of the read logic.
- `upsertSyncQueueEntry` was re-keyed: dedupe is now by `entry.key` (Placement.key), not `idempotency_key`. Each retry rotates the entry's `idempotency_key` field; per-key dedupe means one row per failed placement, updated in place. Added `findSyncQueueEntry(record, key)` helper.

**Dispatch lib (`worker/lib/dispatch.ts`).** New file. Three exports:
- `dispatchPlaceBet(env, pickIndices, source)` — POSTs `repository_dispatch` to GitHub. Returns `{ status: 'ok' }` on 2xx, `{ status: 'failed', error }` otherwise. Source string lets us distinguish `'v2-frontend'` from `'v2-sync-retry'` in the GitHub payload.
- `getCachedDispatchResult(env, email, idempotency_key)` and `cacheDispatchResult(...)` use `dispatch:<email>:<idempotency_key>` KV keys with a 24h `expirationTtl`. Same idempotency_key on a retry returns the cached result; a fresh idempotency_key is treated as a new attempt. ADR 0003's "no TTL" rule is for state records; the dispatch cache is a separate concern with a bounded retry window.

**Routes.** Five new files, each mounting `app.use('*', requireAuth)` and using `safeParse` so a bad body returns 400 with Zod issues instead of throwing.

- `worker/routes/state-placements.ts` — `POST /` validates the body, builds the full Placement (server-stamped `placed_at`), calls `appendPlacement`, returns the merged entry as 201. `DELETE /:key` URL-decodes the key and calls `removePlacement`, returning 204 on success or 404 if no record / no match.
- `worker/routes/state-manual-bets.ts` — same shape. Server-assigned `id = idempotency_key`. `outcome` defaults to `'pending'`.
- `worker/routes/state-sync-queue.ts` — `POST /retry`: idempotency cache check first, then look up the pick in `data.json.picks[]` by `pick + "|" + event === key`. If not found, write a 'Pick no longer in current scan' error to the queue entry and return 404. Otherwise fire `dispatchPlaceBet`, cache the result, write the queue entry with `attempt_count: prior + 1` and `last_error: result.error || null`. Returns 202 on success, 502 on dispatch failure.
- `worker/routes/balance-override.ts` — thin wrapper over `upsertBalanceOverride`. Returns the persisted record.
- `worker/routes/place-bet.ts` — POST /: idempotency cache check, then `dispatchPlaceBet(pick_indices, 'v2-frontend')`, cache, return 202 on success / 502 on failure.

**Mount order (`worker/index.ts`).** Legacy first (`/api/health`, `/api/place-bets`), then v2 read routes, then v2 write routes. More-specific `/api/state/*` paths are mounted BEFORE `/api/state` itself for defensive readability, though a one-shot Hono smoke test confirmed the order does not actually matter (Hono scopes wildcard middleware to its own subapp, not the broader prefix). The smoke test was deleted after confirming.

**Verification.** `npx tsc -b` clean. Live `wrangler dev` smoke still blocked by EMFILE from session 2; deferred to step 9.

### Phase 1 step 8 (Cloudflare Access dashboard): runbook drafted

[`docs/cloudflare-access-setup.md`](docs/cloudflare-access-setup.md) is the click-by-click. Recommended path scope is `/api/*` for cohabitation (legacy `index.html` keeps loading at the root path; new v2 API routes are auth-gated). Expand to `/*` after step 9 cutover. The runbook includes verification steps, IdP setup if Google is not yet configured on the account, and rollback. Worker code does not change; this step is pure dashboard config.

### Phase 1 step 9 (EMFILE fix): what shipped

**Root cause.** Two layers had to be teased apart:

1. `wrangler.jsonc` had `assets.directory: "."`, which made the wrangler dev file watcher walk the whole repo (worker source, node_modules, `.git`, `.claude/worktrees/*`, scripts, mockups, every Python module). On macOS, launchd's default per-process file-descriptor soft limit is **256** even when `ulimit -n` reports 1M+ for the shell (`launchctl limit maxfiles` confirms). The wide watch tree exhausted descriptors and crashed with EMFILE within seconds of `wrangler dev` start.
2. `.assetsignore` controls which files wrangler **uploads** at deploy and **serves** from the assets binding. It does NOT affect the dev watcher. Adding `.assetsignore` alone did not resolve EMFILE; verified empirically before settling on the right fix.

**Fix.**
- Created `public/` with three **symlinks** pointing one level up: `public/index.html → ../index.html`, `public/data.json → ../data.json`, `public/bankroll.json → ../bankroll.json`. Symlinks (not hardlinks) so future code that writes via temp+rename still resolves correctly via the symlink at access time.
- Updated `wrangler.jsonc` `assets.directory: "."` → `"public"`. Watcher now walks 3 entries instead of thousands.
- The Python cron writes to repo-root `data.json` and `bankroll.json` unchanged; symlinks make the writes visible to the worker without touching the model code.
- `.assetsignore` added as defense-in-depth: default-deny posture, allowlists only `index.html`, `data.json`, `bankroll.json`. Side benefit: stops the public site from serving `pick_history.json` (535 KB of model calibration data) which had no reason to be on the public URL.

**Verification.** `wrangler dev` now starts in ~1 second (READY at iteration 1, no EMFILE). Smoked all 9 v2 routes against the local server with a mocked `cf-access-authenticated-user-email` header:

- `GET /api/health` → 200 `{"ok":true,"time":"..."}` (legacy, no auth needed)
- `GET /api/me` without header → 401. With header → 200 `{"email":"...","picture_url":null}`.
- `GET /api/picks` → 200 with normalized payload. **`scan_subtitle` is "Thursday, April 30, 2026 - MLB (11), NBA (3), NHL (2)"** (em-dash stripped to hyphen, confirmed against the source `—` in the symlinked data.json).
- `GET /api/bankroll` → 200 `{"available":679.34,"starting":500,"profit":179.34,"lifetime":{...},"balance_override":null}`. After POST `/api/balance-override {"amount":700,"note":"smoke test"}` → `available:700` and `balance_override:{...}` populated. KV merge confirmed.
- `GET /api/state` → 200 empty arrays + `updated_at:null` initially. After POST `/api/state/placements` (same idempotency_key sent twice) → only ONE placement in the merged record. Idempotency dedupe confirmed.
- `POST /api/state/manual-bets` → 201 with server-assigned `id = idempotency_key`, `outcome:"pending"`.
- `DELETE /api/state/placements/<URL-encoded-key>` → 204 No Content. URL decoding of `%20`, `%2B`, `%7C`, `%40` works.
- Bad body to any POST → 400 with detailed Zod issues array.

The local KV writes during the smoke live in `.wrangler/` (miniflare, not real Cloudflare KV). `.gitignore` covers `.wrangler/`.

### What's next (continue here on resume)

**Phase 1 wraps when Max completes step 8 in the dashboard.** No more code work needed for Phase 1 itself; the runbook at `docs/cloudflare-access-setup.md` is the input.

**Phase 2 (quality gate)** is the next code work block:
1. Vitest harness for `lib/picks.ts` normalizer (covers em-dash strip, percent-string coercion, dollars-string coercion, missing-field defaults, scan_age_seconds calculation). The empty-picks case is also worth a test since today's data.json is exactly that.
2. Route tests with `wrangler unstable_dev` (or just direct `app.fetch(new Request(...))` calls like the one-shot Hono smoke from step 7) for at least the read routes. Write routes are harder to test in isolation because of the GitHub dispatch side effect; mock or skip for now.
3. Smoke against the live URL post-Access via the Cloudflare access JWT (or by curling with the dev mock locally and trusting parity). Live smoke should hit `/api/me`, `/api/picks`, `/api/bankroll`, `/api/state` and confirm 200 + correct shape.

**Phase 3 (cutover)** is later:
1. Build the v2 frontend (`npm run build`) and place output at `public/` (replaces or coexists with the legacy `index.html` symlink).
2. Move legacy `index.html` to `legacy/index.html` for one-week fallback at `/legacy`.
3. Remove the legacy `/api/place-bets` (plural) route after one week of v2 SPA stability.
4. Tighten Cloudflare Access policy from `/api/*` to `/*` once root is the v2 SPA.

---

## 2026-04-30 session 2 (PAUSED, end-of-session, ready for Phase 1)

### Goal
Close Phase 0 of the v2 frontend rebuild. Done. Phase 1 (Vite scaffold + Hono routes + KV namespace + Cloudflare Access policy) starts in the next session.

### What shipped this session

**Phase 0.5: API contract locked.** Ran the `frontend-to-backend-requirements` skill in a 7-question prompted interview. Output at `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`. Two commits: `728d93c` (doc + launch.json), `467d23b` (HANDOFF update).

Decisions (all 7 confirmed via AskUserQuestion):
1. **v2 UX scope**: like-for-like rebuild + auth + cross-device sync. Same 5 tabs, same actions per tab.
2. **Scan-date navigation**: latest scan only, no date picker. /api/picks does not need a scan_date param.
3. **5th tab**: renamed Settings to **Account**. Scope: identity, balance override, sign-out, lifetime stats. No model config.
4. **Sync conflict**: append-merge. Frontend POSTs single events; worker merges into KV. No whole-state PUTs.
5. **Place-bet failure UX**: "queued for retry" badge per row, KV-backed sync_queue, cross-device synced. Retry Now button.
6. **/api/picks shape**: reshape into clean v2 types. Worker normalizes numerics, drops redundant fields, strips em-dashes.
7. **Manual bets**: same narrow scope as today (Place button on rejected no-edge rows + wager prompt). No freeform off-platform logging.

Suggested endpoint surface (subject to backend confirmation in Phase 1):
- `GET /api/me`, `GET /api/picks`, `GET /api/bankroll`, `GET /api/state`
- `POST /api/state/placements`, `DELETE /api/state/placements/:key`
- `POST /api/state/manual-bets`, `DELETE /api/state/manual-bets/:id`
- `POST /api/state/sync-queue/retry`
- `POST /api/balance-override`
- `POST /api/place-bet` (existing GitHub dispatch + idempotency token)

**Phase 0.6: KV state schema.** Wrote `docs/adr/0003-state-schema.md` directly (the database-schema-designer skill is SQL-focused; relevant context fit in the ADR). Decisions:
- KV namespace `EDGE_STATE`, two key prefixes: `state:<email>:<scan_date>` and `balance_override:<email>`.
- Email is lowercased in keys (Cloudflare Access returns whatever case Google sent).
- `scan_date` is ISO `YYYY-MM-DD`. Lex sort equals chrono sort, list-by-prefix comes for free.
- Value blobs carry `schema_version: 1`. Future shape changes upgrade in-place on read.
- No TTL (records are tiny, late-resolving bets need to stick around).
- Append-merge with client-generated idempotency keys for dedupe.
- Alternatives considered (rejected): D1, per-event keys, Durable Objects, storing state in data.json (the cron would clobber it; the bets[] sanctity rule from lessons.md 2026-03-18 explicitly protects against that pattern).

Wrangler dev dev-server config exists in `.claude/launch.json` (alongside `site` on 8080 and `mockups` on 8090) but currently fails with `EMFILE: too many open files, watch` because `assets.directory: "."` makes wrangler watch the entire repo (node_modules + 535 kB pick_history.json). Documented in commit `728d93c`. Fix is a Phase-1 concern (add `.assetsignore` or pin assets to a `public/` subdir). Skipped for this session per Max's call.

### Pre-flight ran
`git stash list` empty before pull. `git fetch && git pull --rebase` clean (already up to date). Branch was 5 ahead of origin/main, 0 behind. Stash list confirmed empty afterward.

### Resolved this session
Nothing model-side. Pure planning + ADR work.

### Phase 0.7 done. Phase 0 is closed.
Wrote the remaining two ADRs directly (no skill needed; both decisions were already in the plan):
- `docs/adr/0001-stack.md` (Vite + React + TypeScript; Hono on Cloudflare Workers; @cloudflare/vite-plugin for the dev loop; TanStack Query for server state; Zod for shared schemas; hand-rolled CSS). Alternatives rejected: Next.js, Remix, SvelteKit, plain HTML/JS, MUI, Tailwind.
- `docs/adr/0002-auth.md` (Cloudflare Access with Google IdP; worker reads `cf-access-authenticated-user-email` from request header, lowercases in middleware before keying KV; sign-out via `/cdn-cgi/access/logout`). Alternatives rejected: Firebase Auth (tried in March, abandoned), Auth0/Clerk, custom OAuth, Sign in with Apple, anonymous.

Commit: `79287b3 chore(phase-0.7): add ADRs 0001 (stack) and 0002 (auth)`.

### Next is Phase 1 (implementation)
Phase 1 has no skill ceremony; it is real code. Sequence:
1. From repo root: `npm create vite@latest frontend -- --template react-ts`. Vite scaffolds `frontend/`.
2. `cd frontend && npm install` then `npm install -D @cloudflare/vite-plugin`. Configure `vite.config.ts` to use the plugin.
3. Rewrite `worker/index.js` as `worker/index.ts` mounting Hono. Install `hono` + `zod`. Move route handlers into `worker/routes/*.ts` per the folder shape Phase 0.4 scaffolded.
4. Create the KV namespace: `npx wrangler kv:namespace create EDGE_STATE`. Paste the namespace id into `wrangler.jsonc` under `kv_namespaces`. Also create `EDGE_STATE_PREVIEW` for `wrangler dev`.
5. Add `worker/middleware/auth.ts` per ADR 0002. Mount via `app.use('/api/*', requireAuth)`.
6. Implement the route handlers per the locked contract. Start with read paths (`/api/me`, `/api/picks`, `/api/bankroll`, `/api/state`), then write paths (`/api/state/*`, `/api/balance-override`, `/api/place-bet`).
7. Configure the Cloudflare Access policy in the dashboard: app at `dk-edge-finder.max-sheahan.workers.dev/*`, IdP = Google, allow `max.sheahan@icloud.com`. Verify in a private browser window.
8. Wire `wrangler.jsonc` for cohabitation: serve the new build under `/v2/*` and the old `index.html` everywhere else until cutover.
9. Address the wrangler-dev `EMFILE` issue from this session: add `.assetsignore` to skip `dk-edge-finder-app/`, `pick_history.json`, dashboard HTML files, etc., OR pin `assets.directory` to a `frontend/dist/` subdir.

Phase 2 (quality gate) and Phase 3 (cutover) follow per the plan file.

### If you just have one minute, do this
Open the three ADRs in `docs/adr/` to confirm they read correctly. Then run step 1 above (`npm create vite@latest frontend -- --template react-ts`) when you are ready to start Phase 1. The ADRs are the input; Phase 1 is the build.

---

## 2026-04-30 session 1 (paused earlier, ~13:00 PT, picked up by session 2)

### Goal
Rebuild the frontend of [dk-edge-finder.max-sheahan.workers.dev](https://dk-edge-finder.max-sheahan.workers.dev/) with real Google auth and cross-device state. Python model + GitHub Actions cron stay untouched.

### Current branch
`rebuild/v2-frontend` at `52665ab`, branched off `main` and last rebased onto `c08a0e3`. Repo: [blueandyellow44/dk-edge-finder](https://github.com/blueandyellow44/dk-edge-finder), local at `~/Betting Skill`. Branch is pushed to origin.

`main` is at `c08a0e3` and in sync with origin.

### Approved plan
[/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md](/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md)

### Decisions on the books
1. **Scope:** Frontend + new backend pieces (Google auth + shared state store). Python scan model untouched.
2. **Location:** In place at `~/Betting Skill`, on `rebuild/v2-frontend`, frontend folder named `frontend/`.
3. **Stack:** Vite + React for UI. Hono on Cloudflare Workers for API. `@cloudflare/vite-plugin` for the dev loop.
4. **Auth:** Cloudflare Access with Google IdP. Worker reads `cf-access-authenticated-user-email` to identify user.
5. **State store:** Workers KV namespace `EDGE_STATE`. Records keyed by `(user_email, scan_date)` for placements + sync_queue + manual_bets, plus a single `balance_override:{email}` record.
6. **Python output target:** No change. Model continues to write `data.json`, `bankroll.json`, `pick_history.json` to git.

### What shipped this session (8 commits)

**Model fixes on main:**
1. `8fd86b7 fix(resolver): key scoreboard cache by (sport, date), not just sport`
2. `a3efced data: resolve 110 backlogged NBA paper picks (Apr 5-29)`
3. `fe63294 fix(model): NBA playoff discount + hard skip on too-good-to-be-true edges`
4. `c08a0e3 data: re-scan today with playoff discount applied (0 edges)`

**Rebuild scaffolding on rebuild/v2-frontend:**
5. `2945fea chore: add v2 rebuild scaffolding docs (lessons, handoff, changelog)`
6. `8e98eb8 chore: update HANDOFF + CHANGELOG with NBA playoff discount fix`
7. `220170f chore(scaffold): pre-scaffold worker/, shared/, docs/adr/ folder tree`
8. `52665ab chore: update HANDOFF.md, Phase 0.4 done, next is Phase 0.5`

Detail on the model fixes:
- **Resolver cache-key bug.** `scripts/resolve_bets.py` was caching scoreboards under `all_games[sport]`, which silently reused the wrong date's scoreboard for second-and-later pending picks of the same sport. 110 NBA picks across April 5-29 had been stuck pending for weeks. Fix lives in both `main()` and `resolve_pick_history()`. Branch `fix/resolver-cache-key` merged.
- **NBA playoff discount.** Adds `is_nba_playoff_window()` plus 5 calibration constants. During Apr 15 to Jun 30: NBA edge reduced 40%, NBA OVER totals reduced an additional 10%, NBA min-edge raised to 8%, hard skip on anything still above 10% post-discount. Today's `OVER 212.5 BOS @ PHI` (29.3% raw) was correctly hard-skipped. Branch `fix/nba-playoff-discount` merged.

### Resolved this session (do NOT re-open)
- **Resolver `main()` cache-key bug.** Fixed alongside `resolve_pick_history()`. The placed-bet path also had the smaller related issue. Both paths now key by `(sport, date)`.

### Calibration snapshots captured
- `/tmp/dk-edge-calibration-BASELINE.txt` (pre-resolver-fix, masked NBA losses)
- `/tmp/dk-edge-calibration-AFTER-FIX.txt` (post-resolver-fix, true picture, NBA at 44.9% / -$252.63 over 178 picks)

### Detour findings filed in [dk-edge-finder/tasks/lessons.md](dk-edge-finder/tasks/lessons.md) (this branch only)
1. Resolver cache-key fix [AUTOMATE - DONE]
2. NBA model unprofitable: 44.9% over 178, paper P/L -$252.63 [BACKLOG]
3. 5-8% edge bucket below break-even at 52.8% over 271 [BACKLOG]
4. Stale-stash awareness rule [MANUAL]

### Phase 0.4 done (file-architect output)
All 6 folder-architect questions answered, folder tree scaffolded.

Recorded answers:
1. Frontend folder: `frontend/` (Vite scaffolds it in Phase 1, NOT pre-created here)
2. Old `index.html`: stays at root during cohabitation, Worker routes around it
3. Shared types: `shared/` at repo root
4. Worker layout: keep folder name `worker/`, split into `worker/index.ts` + `worker/routes/` + `worker/middleware/` + `worker/lib/` (rewrite from .js to .ts in Phase 1)
5. Mockups: existing `mockups/` keeps being the home, prefix new files with `v2-`
6. ADRs: `docs/adr/0001-stack.md`, `0002-auth.md`, `0003-state-schema.md`

Folders created with `.gitkeep`: `worker/routes/`, `worker/middleware/`, `worker/lib/`, `shared/`, `docs/adr/`. Existing `worker/index.js` untouched. Live site continues serving from it.

### Phase 0.5 (closed in session 2)
Was: invoke the `frontend-to-backend-requirements` skill, lock the API contract. Done. Locked decisions and the 11 suggested endpoints (more than the original 7-endpoint sketch below) live in `.claude/docs/ai/dk-edge-v2-frontend/backend-requirements.md`. The original endpoint sketch from this session-1 record is superseded:
- `GET /api/me`, `GET /api/picks`, `GET /api/bankroll`, `GET /api/state` (no scan_date param needed by default, Q2)
- `POST /api/state/placements`, `DELETE /api/state/placements/:key` (append-merge, Q4)
- `POST /api/state/manual-bets`, `DELETE /api/state/manual-bets/:id`
- `POST /api/state/sync-queue/retry` (cross-device retry, Q5)
- `POST /api/balance-override`
- `POST /api/place-bet` (idempotency token added; addresses HIGH backlog)

### Open backlog (priorities are proposals, correct as needed)

**HIGH (do during the rebuild)**
- **`/api/place-bet` idempotency.** Current Worker route has no idempotency token, so two simultaneous Place clicks dispatch twice. Worth fixing during the rebuild before the new frontend ships its retry logic. File: `worker/index.js:36-159`.
- **GitHub Actions Node 20 deprecation on June 2, 2026.** Bump `actions/checkout@v4` and `actions/setup-python@v5` to versions that support Node.js 24. All four `.github/workflows/*.yml` files affected. Hard deadline.

**MEDIUM (next 2-4 weeks)**
- **NBA model recalibration.** The tactical playoff-discount patch shipped today is not a real recalibration. Real fix: pull historical NBA playoff data, train a separate playoff-aware model, compare to RS model, tune discount factors. Filed in `dk-edge-finder/tasks/lessons.md` as [BACKLOG].
- **5-8% edge bucket policy.** Sits at 52.8% / -$156.32 over 271, just below the 52.4% break-even at -110 odds. Either raise base min-edge from 5% to 8% or stiffen the graduated discount. Filed in `dk-edge-finder/tasks/lessons.md` as [BACKLOG].
- **Stuck-pending picks (props).** 106 still pending after the resolver fix. Most are player props the existing resolver cannot handle (no per-player stat fetcher). Building a prop resolver is a separate model-side task.

**LOW (whenever)**
- **Stale `claude/*` worktree branches.** `claude/condescending-lovelace`, `claude/gallant-jemison`, `claude/silly-varahamihira`, `claude/tender-haslett`, `claude/tender-mahavira`, `claude/tender-villani`, `claude/tender-wiles`, `claude/trusting-bassi`, plus `claude/laughing-brown`. Some are 30+ days old. Worth pruning with `git branch -D` and `git push origin --delete` after confirming nothing in-progress lives on them.
- **ODDS_API_KEY rotation.** Last rotated 2026-03-21 (~40 days old). No expiry signal yet. Low priority but worth tracking.

### Useful paths
- Repo root: `~/Betting Skill`
- Plan file: `/Users/maxsheahan/.claude/plans/i-am-trying-to-prancy-teapot.md`
- Rebuild lessons (root): `~/Betting Skill/lessons.md`
- Model lessons: `~/Betting Skill/dk-edge-finder/tasks/lessons.md`
- Changelog: `~/Betting Skill/CHANGELOG.md`
- Current single-file frontend: `~/Betting Skill/index.html` (66 kB, will be replaced at cutover)
- Current Worker: `~/Betting Skill/worker/index.js`
- Wrangler config: `~/Betting Skill/wrangler.jsonc`
- Python model: `~/Betting Skill/scripts/`
- Skill folder: `~/.claude/skills/dk-edge-finder/`
- Stale React/Firebase rebuild attempt (March 17, abandoned): `~/Betting Skill/dk-edge-finder-app/`

### Useful commands
```
# ALWAYS before working, and ALWAYS list stashes first (lesson 2026-04-30)
cd ~/Betting\ Skill
git stash list           # if anything is here, decide whether to drop BEFORE pulling
git stash && git pull --rebase && git stash pop
git stash list           # confirm clean afterwards

# Run the model locally (free APIs, no Odds API credit cost)
python3 scripts/scan_edges.py --games-only
python3 scripts/resolve_bets.py
python3 scripts/analyze_history.py

# Worker dev loop (post-Phase-1)
wrangler dev

# Inspect cron runs
gh run list --repo blueandyellow44/dk-edge-finder --limit 10
gh run view <run_id> --log

# Compare local main to remote (for stale-checkout drift detection)
git fetch origin main && git rev-list --left-right --count main...origin/main
```

### Known live values (snapshot, will drift over time)
- Snapshot timestamp: **2026-04-30 13:00 PT**
- Live bankroll on origin/main: $679.34 (per April 29 Full Scan, may have moved if cron picks were resolved overnight; check `git show HEAD:bankroll.json | jq .balance_override` to verify)
- Today's edges on origin/main: **0** (correctly empty after the playoff discount + line movement; next cron at 19 UTC will refresh)
- Resolved-record after the resolver fix: 415W-315L on 730 resolved picks
- ODDS_API_KEY age: ~40 days old (last rotated 2026-03-21)
