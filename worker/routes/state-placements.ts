import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate } from '../lib/picks'
import { appendPlacement } from '../lib/state'
import { PlacementCreateRequestSchema, PlacementSchema } from '../../shared/schemas'
import type { Placement } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.post('/', async (c) => {
  const email = c.get('email')
  const body = await c.req.json().catch(() => null)
  const parsed = PlacementCreateRequestSchema.safeParse(body)
  if (!parsed.success) {
    return c.json({ error: 'Invalid placement body', issues: parsed.error.issues }, 400)
  }
  if (parsed.data.action === 'placed' && typeof parsed.data.wager !== 'number') {
    return c.json({ error: 'wager is required when action is "placed"' }, 400)
  }
  const scan_date = await getLatestScanDate(c.env)
  const placement: Placement = PlacementSchema.parse({
    key: parsed.data.key,
    action: parsed.data.action,
    dispatch_status: parsed.data.dispatch_status,
    placed_at: new Date().toISOString(),
    idempotency_key: parsed.data.idempotency_key,
    ...(typeof parsed.data.wager === 'number' ? { wager: parsed.data.wager } : {}),
  })
  const record = await appendPlacement(c.env, email, scan_date, placement)
  const merged = record.placements.find((p) => p.idempotency_key === placement.idempotency_key) ?? placement
  return c.json(merged, 201)
})

export default app
