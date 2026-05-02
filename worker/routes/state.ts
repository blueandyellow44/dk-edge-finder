import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate } from '../lib/picks'
import { readState } from '../lib/state'
import { StateResponseSchema } from '../../shared/schemas'
import type { StateResponse } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.get('/', async (c) => {
  const email = c.get('email')
  const scan_date = await getLatestScanDate(c.env)
  const record = await readState(c.env, email, scan_date)

  const response: StateResponse = record
    ? {
        scan_date: record.scan_date,
        placements: record.placements,
        sync_queue: record.sync_queue,
        manual_bets: record.manual_bets,
        updated_at: record.updated_at,
      }
    : {
        scan_date,
        placements: [],
        sync_queue: [],
        manual_bets: [],
        updated_at: null,
      }

  return c.json(StateResponseSchema.parse(response))
})

export default app
