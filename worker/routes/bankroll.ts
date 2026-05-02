import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getBankrollResponse } from '../lib/bankroll'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.get('/', async (c) => {
  const email = c.get('email')
  const payload = await getBankrollResponse(c.env, email)
  return c.json(payload)
})

export default app
