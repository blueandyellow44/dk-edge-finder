import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate } from '../lib/picks'
import { appendManualBet, removeManualBet } from '../lib/state'
import { ManualBetCreateRequestSchema, ManualBetSchema } from '../../shared/schemas'
import type { ManualBet } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.post('/', async (c) => {
  const email = c.get('email')
  const body = await c.req.json().catch(() => null)
  const parsed = ManualBetCreateRequestSchema.safeParse(body)
  if (!parsed.success) {
    return c.json({ error: 'Invalid manual bet body', issues: parsed.error.issues }, 400)
  }
  const scan_date = await getLatestScanDate(c.env)
  // Manual bets are identified by a server-assigned id derived from the
  // idempotency key. Same idempotency_key means same id, which keeps the
  // dedupe in appendManualBet honest across retries.
  const manualBet: ManualBet = ManualBetSchema.parse({
    id: parsed.data.idempotency_key,
    sport: parsed.data.sport,
    event: parsed.data.event,
    pick: parsed.data.pick,
    odds: parsed.data.odds,
    wager: parsed.data.wager,
    outcome: 'pending',
    placed_at: new Date().toISOString(),
    idempotency_key: parsed.data.idempotency_key,
  })
  const record = await appendManualBet(c.env, email, scan_date, manualBet)
  const merged = record.manual_bets.find((b) => b.idempotency_key === manualBet.idempotency_key) ?? manualBet
  return c.json(merged, 201)
})

app.delete('/:id', async (c) => {
  const email = c.get('email')
  const id = decodeURIComponent(c.req.param('id'))
  const scan_date = await getLatestScanDate(c.env)
  const result = await removeManualBet(c.env, email, scan_date, id)
  if (!result.removed) return c.json({ error: 'Manual bet not found' }, 404)
  return c.body(null, 204)
})

export default app
