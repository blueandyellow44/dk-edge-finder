import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getActivityResponse } from '../lib/activity'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.get('/', async (c) => {
  const payload = await getActivityResponse(c.env)
  return c.json(payload)
})

export default app
