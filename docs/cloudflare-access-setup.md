# Cloudflare Access setup runbook (step 8)

Status: **TODO** as of 2026-04-30 (Phase 1 step 8 of v2 rebuild)
Related: [`adr/0002-auth.md`](adr/0002-auth.md), [`../HANDOFF.md`](../HANDOFF.md)

This is the click-by-click for configuring the Cloudflare Access policy that the v2 worker depends on. The worker is already wired to read `cf-access-authenticated-user-email` per ADR 0002; this runbook flips the switch that populates that header.

## Before you start

You will need:
- Login to the Cloudflare account that owns `dk-edge-finder.max-sheahan.workers.dev`.
- Google account `max.sheahan@icloud.com` available in a separate browser window or private window for verification.
- ~10 minutes.

The worker code does NOT need any changes for this step. The middleware in `worker/middleware/auth.ts` already handles the header presence/absence cleanly: missing header returns 401, present header populates `c.get('email')`.

## Recommended scope: protect `/api/*` only initially

The live single-file `index.html` at the root path still calls the legacy `/api/place-bets` (plural) without an Access header. If you protect `/*`, the live site breaks immediately. If you protect `/api/*`, the worker falls into the legacy code path (which serves `index.html` via the ASSETS binding) for the root path and only the new v2 API routes get gated. Legacy `/api/place-bets` becomes Access-protected too, which is fine because the live `index.html` will fail closed (the worker returns 401 for `/api/*` without the header) and you will know immediately.

If that is too aggressive, the safer fallback is to protect ONLY the new v2 routes by listing them explicitly: `/api/me`, `/api/picks`, `/api/bankroll`, `/api/state`, `/api/state/*`, `/api/balance-override`, `/api/place-bet`. Slightly more clicks; lower blast radius.

After step 9 cutover (when the legacy `index.html` retires), expand to `/*`.

## Steps

### 1. Open Zero Trust → Access

1. Cloudflare dashboard: `https://dash.cloudflare.com/`
2. Account view, left sidebar: **Zero Trust**.
3. Inside Zero Trust: **Access** → **Applications**.

If this is your first time using Zero Trust on this account, you may be prompted to pick a team domain (e.g. `dk-edge-finder.cloudflareaccess.com`). Pick something memorable; this is the URL Cloudflare uses for the auth handshake. You can also add a custom domain later.

### 2. Add a self-hosted application

1. Click **Add an application** → **Self-hosted**.
2. **Application name**: `DK Edge Finder v2`.
3. **Session duration**: 24 hours (default is fine; you can shorten if you want more frequent re-auth).
4. **Application domain**: `dk-edge-finder.max-sheahan.workers.dev`.
5. **Path** (the recommended-scope decision from above):
    - Recommended: `/api/*`
    - Conservative fallback: leave blank, then add a separate application per v2 route prefix
6. Leave the rest at defaults. Click **Next**.

### 3. Add Google as the identity provider

1. **Identity providers**: select **Google** if it is already configured for this account.
2. If Google is NOT yet configured:
    - Open a second tab to **Settings** → **Authentication** → **Login methods** → **Add new** → **Google**.
    - You will need a Google OAuth client (client ID + secret) from `https://console.cloud.google.com/`. Standard OAuth 2.0 Web application credentials. Authorized redirect URIs: the value Cloudflare displays on the IdP setup page.
    - Save, then return to the application setup tab.
3. Click **Next**.

### 4. Add the Allow policy

1. **Policy name**: `Allow Max`.
2. **Action**: **Allow**.
3. **Configure rules** → **Include** → **Emails** → enter `max.sheahan@icloud.com`.
4. Click **Next**, then **Add application**.

### 5. Verify

1. Open a private/incognito window.
2. Visit `https://dk-edge-finder.max-sheahan.workers.dev/api/me`.
3. Expected: Cloudflare's branded sign-in page → Google OAuth → land on a JSON response like `{"email":"max.sheahan@icloud.com","picture_url":"https://lh3.googleusercontent.com/..."}` (picture_url may be null if Google did not return a picture claim; the v2 frontend handles that with initials).
4. If you get 401 instead, the Access policy did not attach to the path. Re-check step 2.5 (path scope).

Smoke each new v2 read route the same way:
- `/api/picks` → `{"scan_date":"2026-04-30", "scan_subtitle": "...", "picks": [], ...}` (today is zero-edges).
- `/api/bankroll` → `{"available": 679.34, "starting": 500, "profit": 179.34, "lifetime": {...}, "balance_override": null}`.
- `/api/state` → `{"scan_date": "2026-04-30", "placements": [], "sync_queue": [], "manual_bets": [], "updated_at": null}` (empty until you POST any state).

Smoke a write route:
- `curl -X POST -H 'Content-Type: application/json' -d '{"amount": 700.00, "note": "test"}' 'https://dk-edge-finder.max-sheahan.workers.dev/api/balance-override'`
- Expected: 401 from a normal `curl` because there is no Access cookie.
- For real verification, the v2 frontend (Phase 2) will exercise these via the browser session.

## Rollback

If anything breaks the live site:
1. Cloudflare dashboard → Zero Trust → Access → Applications.
2. Click the `DK Edge Finder v2` application → **Edit**.
3. Either change the path scope back to something narrower, OR delete the application entirely.
4. The worker code does not change; removing the Access policy means the `cf-access-authenticated-user-email` header stops being populated and the v2 routes return 401, but the legacy `/api/health` and `/api/place-bets` paths and the static `index.html` keep working unchanged.

## After this is done

Move to step 9 (`.assetsignore` + `assets.directory` fix). The HANDOFF.md `What's next` block has the sequence.
