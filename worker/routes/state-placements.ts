import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate } from '../lib/picks'
import { appendPlacement, removePlacement } from '../lib/state'
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
  const scan_date = await getLatestScanDate(c.env)
  const placement: Placement = PlacementSchema.parse({
    key: parsed.data.key,
    action: parsed.data.action,
    dispatch_status: parsed.data.dispatch_status,
    placed_at: new Date().toISOString(),
    idempotency_key: parsed.data.idempotency_key,
  })
  const record = await appendPlacement(c.env, email, scan_date, placement)
  const merged = record.placements.find((p) => p.idempotency_key === placement.idempotency_key) ?? placement
  return c.json(merged, 201)
})

app.delete('/:key', async (c) => {
  const email = c.get('email')
  const key = decodeURIComponent(c.req.param('key'))
  const scan_date = await getLatestScanDate(c.env)
  const result = await removePlacement(c.env, email, scan_date, key)
  if (!result.removed) return c.json({ error: 'Placement not found' }, 404)
  return c.body(null, 204)
})

export default app
