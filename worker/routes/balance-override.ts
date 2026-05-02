import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { upsertBalanceOverride } from '../lib/state'
import { BalanceOverrideRequestSchema } from '../../shared/schemas'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.post('/', async (c) => {
  const email = c.get('email')
  const body = await c.req.json().catch(() => null)
  const parsed = BalanceOverrideRequestSchema.safeParse(body)
  if (!parsed.success) {
    return c.json({ error: 'Invalid balance override body', issues: parsed.error.issues }, 400)
  }
  const record = await upsertBalanceOverride(c.env, email, parsed.data.amount, parsed.data.note)
  return c.json(record, 200)
})

export default app
