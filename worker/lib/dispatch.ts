import type { Env } from '../env'
import type { PlaceBetResponse } from '../../shared/types'
import { PlaceBetResponseSchema } from '../../shared/schemas'

const REPO_OWNER = 'blueandyellow44'
const REPO_NAME = 'dk-edge-finder'
const DISPATCH_EVENT_TYPE = 'place-bets'

// 24h TTL on the dedupe cache. Legitimate retries fire within seconds to
// minutes; the 24h ceiling is just a defense against indefinite key bloat
// while staying well past any reasonable retry window.
const DISPATCH_CACHE_TTL_SECONDS = 86_400

function dispatchCacheKey(email: string, idempotency_key: string): string {
  return `dispatch:${email}:${idempotency_key}`
}

export async function getCachedDispatchResult(
  env: Env,
  email: string,
  idempotency_key: string,
): Promise<PlaceBetResponse | null> {
  const raw = await env.EDGE_STATE.get(dispatchCacheKey(email, idempotency_key))
  if (!raw) return null
  try {
    return PlaceBetResponseSchema.parse(JSON.parse(raw))
  } catch {
    return null
  }
}

export async function cacheDispatchResult(
  env: Env,
  email: string,
  idempotency_key: string,
  result: PlaceBetResponse,
): Promise<void> {
  const validated = PlaceBetResponseSchema.parse(result)
  await env.EDGE_STATE.put(
    dispatchCacheKey(email, idempotency_key),
    JSON.stringify(validated),
    { expirationTtl: DISPATCH_CACHE_TTL_SECONDS },
  )
}

export async function dispatchPlaceBet(
  env: Env,
  pickIndices: number[],
  source: string,
): Promise<PlaceBetResponse> {
  if (!env.GITHUB_TOKEN) {
    return { status: 'failed', error: 'Server misconfigured: GITHUB_TOKEN secret not set' }
  }

  const res = await fetch(`https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/dispatches`, {
    method: 'POST',
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'dk-edge-finder-worker',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      event_type: DISPATCH_EVENT_TYPE,
      client_payload: {
        picks: pickIndices.join(','),
        triggered_at: new Date().toISOString(),
        source,
      },
    }),
  })

  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    return { status: 'failed', error: `GitHub dispatch ${res.status}: ${detail.slice(0, 300)}` }
  }

  return { status: 'ok' }
}
