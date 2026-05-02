import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getPicksResponse } from '../lib/picks'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.get('/', async (c) => {
  const payload = await getPicksResponse(c.env)
  return c.json(payload)
})

export default app
