import { Hono } from 'hono'
import type { Env } from '../env'

const REPO_OWNER = 'blueandyellow44'
const REPO_NAME = 'dk-edge-finder'
const DISPATCH_EVENT_TYPE = 'place-bets'

const ALLOWED_ORIGINS = ['https://dk-edge-finder.max-sheahan.workers.dev']

const app = new Hono<{ Bindings: Env }>()

app.options('/', (c) => corsResponse(c.req.raw))

app.post('/', async (c) => {
  const request = c.req.raw

  const origin = request.headers.get('Origin') ?? ''
  const referer = request.headers.get('Referer') ?? ''
  const sameOrigin = origin === new URL(request.url).origin
  const originOk =
    sameOrigin ||
    ALLOWED_ORIGINS.some((allowed) => origin === allowed || referer.startsWith(allowed))
  if (!originOk) {
    return jsonResponse({ error: 'Forbidden origin', origin, referer }, 403, request)
  }

  if (!c.env.GITHUB_TOKEN) {
    return jsonResponse(
      { error: 'Server misconfigured: GITHUB_TOKEN secret not set' },
      500,
      request,
    )
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return jsonResponse({ error: 'Invalid JSON body' }, 400, request)
  }

  const picksInput = (body as { picks?: unknown } | null)?.picks
  const picks = normalizePicks(picksInput)
  if (!picks) {
    return jsonResponse(
      {
        error:
          'Body must include `picks` as "all", a comma-separated index string, or an array of indices.',
      },
      400,
      request,
    )
  }

  const dispatchRes = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/dispatches`,
    {
      method: 'POST',
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${c.env.GITHUB_TOKEN}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'dk-edge-finder-worker',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        event_type: DISPATCH_EVENT_TYPE,
        client_payload: {
          picks,
          triggered_at: new Date().toISOString(),
          source: 'worker',
        },
      }),
    },
  )

  if (!dispatchRes.ok) {
    const text = await dispatchRes.text().catch(() => '')
    return jsonResponse(
      {
        error: 'GitHub dispatch failed',
        status: dispatchRes.status,
        detail: text.slice(0, 500),
      },
      502,
      request,
    )
  }

  return jsonResponse(
    {
      ok: true,
      dispatched: picks,
      message: 'Workflow dispatched. The bet will appear in data.json within ~1 minute.',
    },
    202,
    request,
  )
})

function normalizePicks(picks: unknown): string | null {
  if (picks === 'all') return 'all'
  if (typeof picks === 'string') {
    if (!/^\d+(,\d+)*$/.test(picks)) return null
    return picks
  }
  if (Array.isArray(picks)) {
    if (picks.length === 0) return null
    if (!picks.every((n) => Number.isInteger(n) && n >= 0)) return null
    return picks.join(',')
  }
  return null
}

function jsonResponse(obj: unknown, status = 200, request: Request | null = null): Response {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  }
  if (request) {
    const origin = request.headers.get('Origin')
    if (origin) {
      headers['Access-Control-Allow-Origin'] = origin
      headers['Access-Control-Allow-Credentials'] = 'true'
      headers['Vary'] = 'Origin'
    }
  }
  return new Response(JSON.stringify(obj, null, 2), { status, headers })
}

function corsResponse(request: Request): Response {
  const origin = request.headers.get('Origin') ?? '*'
  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Max-Age': '86400',
      Vary: 'Origin',
    },
  })
}

export default app
