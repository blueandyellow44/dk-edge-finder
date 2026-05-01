import { describe, test, expect, beforeEach } from 'vitest'
import app from './index'
import type { Env } from './env'

// ────────────────────────────────────────────────────────────────────────
// Mock env: in-memory ASSETS + EDGE_STATE shims, no real Cloudflare runtime.
// ────────────────────────────────────────────────────────────────────────

type AssetsConfig = {
  dataJson?: object
  bankrollJson?: object
  dataLastModified?: string
}

function makeAssets(cfg: AssetsConfig): Env['ASSETS'] {
  return {
    async fetch(input: Request | string): Promise<Response> {
      const url = typeof input === 'string' ? input : input.url
      const path = new URL(url).pathname
      if (path === '/data.json' && cfg.dataJson !== undefined) {
        const headers = new Headers({ 'content-type': 'application/json' })
        if (cfg.dataLastModified) headers.set('last-modified', cfg.dataLastModified)
        return new Response(JSON.stringify(cfg.dataJson), { status: 200, headers })
      }
      if (path === '/bankroll.json' && cfg.bankrollJson !== undefined) {
        return new Response(JSON.stringify(cfg.bankrollJson), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      }
      return new Response('Not Found', { status: 404 })
    },
  } as unknown as Env['ASSETS']
}

function makeKv(): Env['EDGE_STATE'] {
  const store = new Map<string, string>()
  return {
    async get(key: string) {
      return store.has(key) ? (store.get(key) as string) : null
    },
    async put(key: string, value: string) {
      store.set(key, value)
    },
    async delete(key: string) {
      store.delete(key)
    },
    async list() {
      return { keys: Array.from(store.keys()).map((name) => ({ name })), list_complete: true, cacheStatus: null }
    },
  } as unknown as Env['EDGE_STATE']
}

function makeEnv(cfg: AssetsConfig = {}): Env {
  return {
    ASSETS: makeAssets(cfg),
    EDGE_STATE: makeKv(),
    GITHUB_TOKEN: 'test-token-not-used-in-read-routes',
  } as Env
}

const AUTHED = { 'cf-access-authenticated-user-email': 'max.sheahan@icloud.com' }

function reqJson(path: string, init?: RequestInit): Request {
  return new Request(`https://worker.test${path}`, init)
}

const baseDataJson = {
  scan_date: '2026-04-30',
  scan_subtitle: 'Thursday, April 30, 2026 — MLB (11), NBA (3), NHL (2)',
  games_analyzed: 16,
  best_bet: null,
  picks: [],
  no_edge_games: [
    { sport: 'NBA', event: 'NY @ ATL', line: 'NY -2.5', reason: 'Edge below 3% threshold' },
  ],
}

const baseBankrollJson = {
  starting_bankroll: 500.0,
  current_bankroll: 679.34,
  lifetime_bets: 43,
  lifetime_wins: 37,
  lifetime_losses: 21,
  lifetime_pushes: 1,
  lifetime_profit: 179.34,
  roi_pct: 35.87,
}

// ────────────────────────────────────────────────────────────────────────
// Auth: the requireAuth middleware is the gate for every v2 route.
// ────────────────────────────────────────────────────────────────────────

describe('auth gating', () => {
  test('GET /api/me without header returns 401', async () => {
    const res = await app.fetch(reqJson('/api/me'), makeEnv())
    expect(res.status).toBe(401)
    expect(await res.text()).toBe('Unauthorized')
  })

  test('GET /api/picks without header returns 401', async () => {
    const res = await app.fetch(reqJson('/api/picks'), makeEnv())
    expect(res.status).toBe(401)
  })

  test('GET /api/bankroll without header returns 401', async () => {
    const res = await app.fetch(reqJson('/api/bankroll'), makeEnv())
    expect(res.status).toBe(401)
  })

  test('GET /api/state without header returns 401', async () => {
    const res = await app.fetch(reqJson('/api/state'), makeEnv())
    expect(res.status).toBe(401)
  })

  test('email is canonicalized to lowercase by the middleware', async () => {
    // Mixed-case header should still authenticate, and the lowercased form
    // is what flows into KV keys (verified indirectly via /api/state).
    const env = makeEnv({ dataJson: baseDataJson, bankrollJson: baseBankrollJson })
    const res = await app.fetch(
      reqJson('/api/me', {
        headers: { 'cf-access-authenticated-user-email': 'Max.Sheahan@iCloud.com' },
      }),
      env,
    )
    expect(res.status).toBe(200)
    const body = (await res.json()) as { email: string }
    expect(body.email).toBe('max.sheahan@icloud.com')
  })
})

// ────────────────────────────────────────────────────────────────────────
// Health: legacy public route, no auth needed.
// ────────────────────────────────────────────────────────────────────────

describe('GET /api/health', () => {
  test('returns ok + ISO timestamp without auth', async () => {
    const res = await app.fetch(reqJson('/api/health'), makeEnv())
    expect(res.status).toBe(200)
    const body = (await res.json()) as { ok: boolean; time: string }
    expect(body.ok).toBe(true)
    expect(body.time).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
  })
})

// ────────────────────────────────────────────────────────────────────────
// /api/me
// ────────────────────────────────────────────────────────────────────────

describe('GET /api/me', () => {
  test('returns email from auth header with picture_url=null when no JWT', async () => {
    const res = await app.fetch(reqJson('/api/me', { headers: AUTHED }), makeEnv())
    expect(res.status).toBe(200)
    const body = (await res.json()) as { email: string; picture_url: string | null }
    expect(body.email).toBe('max.sheahan@icloud.com')
    expect(body.picture_url).toBeNull()
  })

  test('extracts picture_url from JWT picture claim', async () => {
    // Build a fake JWT with a base64url-encoded payload carrying picture.
    // No signature verification happens (Access already gated the path).
    const claims = { picture: 'https://lh3.googleusercontent.com/a/fake' }
    const headerSeg = base64url(JSON.stringify({ alg: 'none', typ: 'JWT' }))
    const payloadSeg = base64url(JSON.stringify(claims))
    const jwt = `${headerSeg}.${payloadSeg}.signature-placeholder`

    const res = await app.fetch(
      reqJson('/api/me', { headers: { ...AUTHED, 'cf-access-jwt-assertion': jwt } }),
      makeEnv(),
    )
    expect(res.status).toBe(200)
    const body = (await res.json()) as { picture_url: string | null }
    expect(body.picture_url).toBe('https://lh3.googleusercontent.com/a/fake')
  })

  test('falls back to claims.custom.picture when top-level picture is absent', async () => {
    const claims = { custom: { picture: 'https://lh3.googleusercontent.com/a/nested' } }
    const jwt = [
      base64url(JSON.stringify({ alg: 'none', typ: 'JWT' })),
      base64url(JSON.stringify(claims)),
      'sig',
    ].join('.')
    const res = await app.fetch(
      reqJson('/api/me', { headers: { ...AUTHED, 'cf-access-jwt-assertion': jwt } }),
      makeEnv(),
    )
    expect(res.status).toBe(200)
    const body = (await res.json()) as { picture_url: string | null }
    expect(body.picture_url).toBe('https://lh3.googleusercontent.com/a/nested')
  })

  test('returns null picture_url when JWT is malformed', async () => {
    const res = await app.fetch(
      reqJson('/api/me', { headers: { ...AUTHED, 'cf-access-jwt-assertion': 'garbage' } }),
      makeEnv(),
    )
    expect(res.status).toBe(200)
    const body = (await res.json()) as { picture_url: string | null }
    expect(body.picture_url).toBeNull()
  })
})

function base64url(s: string): string {
  // btoa is a global in both the Workers runtime and Node; this matches
  // the worker source style (no @types/node leak into the test).
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

// ────────────────────────────────────────────────────────────────────────
// /api/picks
// ────────────────────────────────────────────────────────────────────────

describe('GET /api/picks', () => {
  test('returns normalized payload, em-dash stripped from scan_subtitle', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(reqJson('/api/picks', { headers: AUTHED }), env)
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      scan_date: string
      scan_subtitle: string
      games_analyzed: number
      picks: unknown[]
      no_edge_games: unknown[]
    }
    expect(body.scan_date).toBe('2026-04-30')
    expect(body.scan_subtitle).toBe('Thursday, April 30, 2026 - MLB (11), NBA (3), NHL (2)')
    expect(body.scan_subtitle).not.toContain('—')
    expect(body.games_analyzed).toBe(16)
    expect(body.picks).toEqual([])
    expect(body.no_edge_games).toHaveLength(1)
  })

  test('500s when the data.json fixture is missing entirely (asset 404)', async () => {
    const env = makeEnv() // no dataJson
    const res = await app.fetch(reqJson('/api/picks', { headers: AUTHED }), env)
    // Hono's onError default returns 500 for unhandled throws.
    expect(res.status).toBe(500)
  })
})

// ────────────────────────────────────────────────────────────────────────
// /api/bankroll
// ────────────────────────────────────────────────────────────────────────

describe('GET /api/bankroll', () => {
  test('returns file values when no per-user override exists in KV', async () => {
    const env = makeEnv({ bankrollJson: baseBankrollJson })
    const res = await app.fetch(reqJson('/api/bankroll', { headers: AUTHED }), env)
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      available: number
      starting: number
      profit: number
      lifetime: { bets: number; wins: number; losses: number; pushes: number; profit: number; roi_pct: number }
      balance_override: unknown
    }
    expect(body.available).toBe(679.34)
    expect(body.starting).toBe(500.0)
    expect(body.profit).toBe(179.34)
    expect(body.lifetime.bets).toBe(43)
    expect(body.lifetime.wins).toBe(37)
    expect(body.lifetime.losses).toBe(21)
    expect(body.lifetime.pushes).toBe(1)
    expect(body.lifetime.roi_pct).toBe(35.87)
    expect(body.balance_override).toBeNull()
  })

  test('per-user KV override wins over file current_bankroll for available', async () => {
    const env = makeEnv({ bankrollJson: baseBankrollJson })
    // Pre-seed the KV override directly (matches what POST /api/balance-override writes).
    const override = {
      schema_version: 1,
      email: 'max.sheahan@icloud.com',
      amount: 750.0,
      note: 'Bumped after Saturday wins',
      updated_at: new Date().toISOString(),
    }
    await env.EDGE_STATE.put(
      `balance_override:max.sheahan@icloud.com`,
      JSON.stringify(override),
    )

    const res = await app.fetch(reqJson('/api/bankroll', { headers: AUTHED }), env)
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      available: number
      balance_override: { amount: number; note: string } | null
    }
    expect(body.available).toBe(750.0)
    expect(body.balance_override).not.toBeNull()
    expect(body.balance_override?.amount).toBe(750.0)
    expect(body.balance_override?.note).toBe('Bumped after Saturday wins')
  })
})

// ────────────────────────────────────────────────────────────────────────
// /api/state
// ────────────────────────────────────────────────────────────────────────

describe('GET /api/state', () => {
  let env: Env

  beforeEach(() => {
    env = makeEnv({ dataJson: baseDataJson })
  })

  test('returns empty arrays + null updated_at when KV has no record', async () => {
    const res = await app.fetch(reqJson('/api/state', { headers: AUTHED }), env)
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      scan_date: string
      placements: unknown[]
      sync_queue: unknown[]
      manual_bets: unknown[]
      updated_at: string | null
    }
    expect(body.scan_date).toBe('2026-04-30')
    expect(body.placements).toEqual([])
    expect(body.sync_queue).toEqual([])
    expect(body.manual_bets).toEqual([])
    expect(body.updated_at).toBeNull()
  })

  test('returns the merged record when KV has state for (email, scan_date)', async () => {
    const record = {
      schema_version: 1,
      email: 'max.sheahan@icloud.com',
      scan_date: '2026-04-30',
      placements: [
        {
          key: 'NYY ML|NYY @ BOS',
          action: 'placed',
          dispatch_status: 'ok',
          placed_at: '2026-04-30T19:05:00Z',
          idempotency_key: 'idem-1',
        },
      ],
      sync_queue: [],
      manual_bets: [],
      updated_at: '2026-04-30T19:05:00Z',
    }
    await env.EDGE_STATE.put(
      'state:max.sheahan@icloud.com:2026-04-30',
      JSON.stringify(record),
    )

    const res = await app.fetch(reqJson('/api/state', { headers: AUTHED }), env)
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      placements: { key: string; idempotency_key: string }[]
      updated_at: string | null
    }
    expect(body.placements).toHaveLength(1)
    expect(body.placements[0].key).toBe('NYY ML|NYY @ BOS')
    expect(body.placements[0].idempotency_key).toBe('idem-1')
    expect(body.updated_at).toBe('2026-04-30T19:05:00Z')
  })
})

// ────────────────────────────────────────────────────────────────────────
// Mount-order regression: the /api/state/* sub-routes must NOT be swallowed
// by the broader /api/state router's middleware (which mounts requireAuth
// at '*'). Step 7's one-shot smoke verified this; codify it here.
// ────────────────────────────────────────────────────────────────────────

describe('mount order: /api/state/* sub-paths route to their own subapps', () => {
  test('POST /api/state/placements does not 404 under the /api/state catch-all', async () => {
    // The subapp validates the body via Zod; an empty body returns 400.
    // The point of this test is that we get a 400 from the placements
    // subapp (not a 404 from being misrouted).
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({}),
      }),
      env,
    )
    expect(res.status).not.toBe(404)
    // Bad body → Zod 400 from the placements subapp.
    expect([400, 422]).toContain(res.status)
  })
})

// ────────────────────────────────────────────────────────────────────────
// Write routes (non-dispatch). These touch only KV and the data.json
// scan-date lookup, so they slot into the existing mock harness directly.
// The dispatch-touching write routes (POST /api/state/sync-queue/retry,
// POST /api/place-bet) need a fetch-injection seam in worker/lib/dispatch.ts
// before they can be unit-tested without a real GitHub call. Tracked as a
// separate piece of work; tests for those land in a follow-up commit.
// ────────────────────────────────────────────────────────────────────────

const SCAN_KEY = 'state:max.sheahan@icloud.com:2026-04-30'

describe('POST /api/state/placements', () => {
  test('creates a placement, server-stamps placed_at, returns 201', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const before = new Date().toISOString()
    const res = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          key: 'NYY ML|NYY @ BOS',
          action: 'placed',
          dispatch_status: 'ok',
          idempotency_key: 'idem-create-1',
        }),
      }),
      env,
    )
    expect(res.status).toBe(201)
    const body = (await res.json()) as {
      key: string
      action: 'placed' | 'skipped'
      dispatch_status: 'ok' | 'queued' | 'failed'
      placed_at: string
      idempotency_key: string
    }
    expect(body.key).toBe('NYY ML|NYY @ BOS')
    expect(body.action).toBe('placed')
    expect(body.dispatch_status).toBe('ok')
    expect(body.idempotency_key).toBe('idem-create-1')
    // placed_at is server-stamped: it should be an ISO timestamp at or
    // after the request started.
    expect(body.placed_at >= before).toBe(true)

    // KV side-effect: the placement is in the merged record.
    const stored = await env.EDGE_STATE.get(SCAN_KEY)
    expect(stored).not.toBeNull()
    const record = JSON.parse(stored as string) as { placements: { idempotency_key: string }[] }
    expect(record.placements).toHaveLength(1)
    expect(record.placements[0].idempotency_key).toBe('idem-create-1')
  })

  test('idempotency_key dedupes: same key sent twice = one placement', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const body = {
      key: 'NYY ML|NYY @ BOS',
      action: 'placed' as const,
      dispatch_status: 'ok' as const,
      idempotency_key: 'idem-dupe',
    }
    const headers = { ...AUTHED, 'content-type': 'application/json' }
    const r1 = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      }),
      env,
    )
    const r2 = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      }),
      env,
    )
    expect(r1.status).toBe(201)
    expect(r2.status).toBe(201)
    const stored = JSON.parse((await env.EDGE_STATE.get(SCAN_KEY)) as string) as {
      placements: { idempotency_key: string }[]
    }
    expect(stored.placements).toHaveLength(1)
  })

  test('dispatch_status defaults to "ok" when omitted from the body', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          key: 'NYY ML|NYY @ BOS',
          action: 'skipped',
          idempotency_key: 'idem-default',
        }),
      }),
      env,
    )
    expect(res.status).toBe(201)
    const body = (await res.json()) as { dispatch_status: string }
    expect(body.dispatch_status).toBe('ok')
  })

  test('rejects bad body with 400 and Zod issues', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({ key: 'x' }),
      }),
      env,
    )
    expect(res.status).toBe(400)
    const body = (await res.json()) as { error: string; issues: unknown[] }
    expect(body.error).toMatch(/Invalid placement body/i)
    expect(Array.isArray(body.issues)).toBe(true)
  })

  test('rejects without auth header', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          key: 'x',
          action: 'placed',
          dispatch_status: 'ok',
          idempotency_key: 'idem-noauth',
        }),
      }),
      env,
    )
    expect(res.status).toBe(401)
  })
})

describe('DELETE /api/state/placements/:key', () => {
  test('removes the placement and returns 204', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    // Seed a placement so DELETE has something to remove.
    await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          key: 'NYY ML|NYY @ BOS',
          action: 'placed',
          dispatch_status: 'ok',
          idempotency_key: 'idem-to-delete',
        }),
      }),
      env,
    )

    const encoded = encodeURIComponent('NYY ML|NYY @ BOS')
    const res = await app.fetch(
      new Request(`https://worker.test/api/state/placements/${encoded}`, {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(204)
    const text = await res.text()
    expect(text).toBe('')

    const stored = JSON.parse((await env.EDGE_STATE.get(SCAN_KEY)) as string) as {
      placements: unknown[]
    }
    expect(stored.placements).toHaveLength(0)
  })

  test('returns 404 when no state record exists at all', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request(`https://worker.test/api/state/placements/${encodeURIComponent('nope|nope')}`, {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(404)
  })

  test('returns 404 when the key is not in the placements array', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    // Seed a different key.
    await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          key: 'A|A',
          action: 'placed',
          dispatch_status: 'ok',
          idempotency_key: 'idem-A',
        }),
      }),
      env,
    )
    const res = await app.fetch(
      new Request(`https://worker.test/api/state/placements/${encodeURIComponent('B|B')}`, {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(404)
  })

  test('URL-decodes special characters in the key parameter', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    // Key contains '|' (pick|event separator), space, '@', '+'.
    const rawKey = 'NYY +1.5|NYY @ BOS'
    await app.fetch(
      new Request('https://worker.test/api/state/placements', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          key: rawKey,
          action: 'placed',
          dispatch_status: 'ok',
          idempotency_key: 'idem-encoded',
        }),
      }),
      env,
    )
    const encoded = encodeURIComponent(rawKey)
    expect(encoded).toContain('%20')
    expect(encoded).toContain('%40')
    expect(encoded).toContain('%7C')

    const res = await app.fetch(
      new Request(`https://worker.test/api/state/placements/${encoded}`, {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(204)
  })
})

describe('POST /api/state/manual-bets', () => {
  test('creates a manual bet with server-assigned id = idempotency_key', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/manual-bets', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          sport: 'NBA',
          event: 'BOS @ PHI',
          pick: 'BOS -6.5',
          odds: '-110',
          wager: 12.5,
          idempotency_key: 'idem-mb-1',
        }),
      }),
      env,
    )
    expect(res.status).toBe(201)
    const body = (await res.json()) as {
      id: string
      idempotency_key: string
      outcome: 'pending' | 'win' | 'loss' | 'push'
      placed_at: string
      sport: string
    }
    expect(body.id).toBe('idem-mb-1')
    expect(body.idempotency_key).toBe('idem-mb-1')
    expect(body.outcome).toBe('pending')
    expect(body.sport).toBe('NBA')
    expect(body.placed_at).toMatch(/^\d{4}-\d{2}-\d{2}T/)
  })

  test('idempotency_key dedupes manual bets', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const body = {
      sport: 'NBA',
      event: 'BOS @ PHI',
      pick: 'BOS -6.5',
      odds: '-110',
      wager: 12.5,
      idempotency_key: 'idem-mb-dupe',
    }
    const headers = { ...AUTHED, 'content-type': 'application/json' }
    await app.fetch(
      new Request('https://worker.test/api/state/manual-bets', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      }),
      env,
    )
    await app.fetch(
      new Request('https://worker.test/api/state/manual-bets', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      }),
      env,
    )
    const stored = JSON.parse((await env.EDGE_STATE.get(SCAN_KEY)) as string) as {
      manual_bets: { idempotency_key: string }[]
    }
    expect(stored.manual_bets).toHaveLength(1)
  })

  test('rejects bad body with 400', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/manual-bets', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({ sport: 'NBA' }),
      }),
      env,
    )
    expect(res.status).toBe(400)
    const body = (await res.json()) as { error: string }
    expect(body.error).toMatch(/Invalid manual bet body/i)
  })
})

describe('DELETE /api/state/manual-bets/:id', () => {
  test('removes the manual bet and returns 204', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    await app.fetch(
      new Request('https://worker.test/api/state/manual-bets', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({
          sport: 'NBA',
          event: 'BOS @ PHI',
          pick: 'BOS -6.5',
          odds: '-110',
          wager: 12.5,
          idempotency_key: 'idem-mb-rm',
        }),
      }),
      env,
    )
    const res = await app.fetch(
      new Request('https://worker.test/api/state/manual-bets/idem-mb-rm', {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(204)
    const stored = JSON.parse((await env.EDGE_STATE.get(SCAN_KEY)) as string) as {
      manual_bets: unknown[]
    }
    expect(stored.manual_bets).toHaveLength(0)
  })

  test('returns 404 for a missing manual bet id', async () => {
    const env = makeEnv({ dataJson: baseDataJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/state/manual-bets/nope', {
        method: 'DELETE',
        headers: AUTHED,
      }),
      env,
    )
    expect(res.status).toBe(404)
  })
})

describe('POST /api/balance-override', () => {
  test('upserts the per-user balance override, returns 200 with the persisted record', async () => {
    const env = makeEnv({ bankrollJson: baseBankrollJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/balance-override', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({ amount: 750.0, note: 'Bumped after Saturday wins' }),
      }),
      env,
    )
    expect(res.status).toBe(200)
    const body = (await res.json()) as {
      schema_version: number
      email: string
      amount: number
      note: string
      updated_at: string
    }
    expect(body.schema_version).toBe(1)
    expect(body.email).toBe('max.sheahan@icloud.com')
    expect(body.amount).toBe(750.0)
    expect(body.note).toBe('Bumped after Saturday wins')
    expect(body.updated_at).toMatch(/^\d{4}-\d{2}-\d{2}T/)

    // /api/bankroll subsequently reflects the new override.
    const bk = await app.fetch(reqJson('/api/bankroll', { headers: AUTHED }), env)
    const bkBody = (await bk.json()) as { available: number; balance_override: { amount: number } | null }
    expect(bkBody.available).toBe(750.0)
    expect(bkBody.balance_override?.amount).toBe(750.0)
  })

  test('subsequent POST overwrites the previous override', async () => {
    const env = makeEnv({ bankrollJson: baseBankrollJson })
    const headers = { ...AUTHED, 'content-type': 'application/json' }
    await app.fetch(
      new Request('https://worker.test/api/balance-override', {
        method: 'POST',
        headers,
        body: JSON.stringify({ amount: 750.0, note: 'first' }),
      }),
      env,
    )
    const second = await app.fetch(
      new Request('https://worker.test/api/balance-override', {
        method: 'POST',
        headers,
        body: JSON.stringify({ amount: 800.0, note: 'second' }),
      }),
      env,
    )
    expect(second.status).toBe(200)
    const body = (await second.json()) as { amount: number; note: string }
    expect(body.amount).toBe(800.0)
    expect(body.note).toBe('second')
  })

  test('rejects bad body with 400', async () => {
    const env = makeEnv({ bankrollJson: baseBankrollJson })
    const res = await app.fetch(
      new Request('https://worker.test/api/balance-override', {
        method: 'POST',
        headers: { ...AUTHED, 'content-type': 'application/json' },
        body: JSON.stringify({ amount: 'not-a-number' }),
      }),
      env,
    )
    expect(res.status).toBe(400)
    const body = (await res.json()) as { error: string }
    expect(body.error).toMatch(/Invalid balance override body/i)
  })
})
