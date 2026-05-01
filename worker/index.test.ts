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
