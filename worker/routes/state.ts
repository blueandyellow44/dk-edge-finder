import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate } from '../lib/picks'
import { listAllStateRecords } from '../lib/state'
import { StateResponseSchema } from '../../shared/schemas'
import type { Placement, ManualBet, SyncQueueEntry, StateResponse } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

app.get('/', async (c) => {
  const email = c.get('email')
  const scan_date = await getLatestScanDate(c.env)
  const records = await listAllStateRecords(c.env, email)

  // Flatten placements / manual_bets / sync_queue across every scan_date,
  // attaching scan_date to each entry so the SPA can scope its resolved-key
  // dedupe by date. Without this, a placement made on Monday is unreachable
  // once Tuesday's cron rotates the scan_date.
  const placements: Placement[] = []
  const manual_bets: ManualBet[] = []
  const sync_queue: SyncQueueEntry[] = []
  let latestUpdate: string | null = null
  for (const r of records) {
    for (const p of r.placements) {
      placements.push({ ...p, scan_date: r.scan_date })
    }
    for (const b of r.manual_bets) {
      manual_bets.push({ ...b, scan_date: r.scan_date })
    }
    for (const q of r.sync_queue) sync_queue.push(q)
    if (!latestUpdate || r.updated_at > latestUpdate) latestUpdate = r.updated_at
  }

  const response: StateResponse = {
    scan_date,
    placements,
    sync_queue,
    manual_bets,
    updated_at: latestUpdate,
  }

  return c.json(StateResponseSchema.parse(response))
})

export default app
