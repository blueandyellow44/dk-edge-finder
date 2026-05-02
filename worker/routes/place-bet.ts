import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import {
  cacheDispatchResult,
  dispatchPlaceBet,
  getCachedDispatchResult,
} from '../lib/dispatch'
import { PlaceBetRequestSchema } from '../../shared/schemas'
import type { PlaceBetResponse } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.post('/', async (c) => {
  const email = c.get('email')
  const body = await c.req.json().catch(() => null)
  const parsed = PlaceBetRequestSchema.safeParse(body)
  if (!parsed.success) {
    return c.json({ error: 'Invalid place-bet body', issues: parsed.error.issues }, 400)
  }
  const { pick_indices, idempotency_key } = parsed.data

  const cached = await getCachedDispatchResult(c.env, email, idempotency_key)
  if (cached) {
    return c.json({ ...cached, dispatch_id: idempotency_key } satisfies PlaceBetResponse, 200)
  }

  const result = await dispatchPlaceBet(c.env, pick_indices, 'v2-frontend')
  const enriched: PlaceBetResponse = { ...result, dispatch_id: idempotency_key }
  await cacheDispatchResult(c.env, email, idempotency_key, enriched)
  return c.json(enriched, result.status === 'ok' ? 202 : 502)
})

export default app
