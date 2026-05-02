import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { getLatestScanDate, loadDataJson } from '../lib/picks'
import { findSyncQueueEntry, readState, upsertSyncQueueEntry } from '../lib/state'
import {
  cacheDispatchResult,
  dispatchPlaceBet,
  getCachedDispatchResult,
} from '../lib/dispatch'
import { SyncQueueRetryRequestSchema, SyncQueueEntrySchema } from '../../shared/schemas'
import type { PlaceBetResponse, SyncQueueEntry } from '../../shared/types'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

function findPickIndexByKey(picks: unknown, key: string): number {
  if (!Array.isArray(picks)) return -1
  return picks.findIndex((p) => {
    if (!p || typeof p !== 'object') return false
    const o = p as { pick?: unknown; event?: unknown }
    return `${o.pick}|${o.event}` === key
  })
}

app.post('/retry', async (c) => {
  const email = c.get('email')
  const body = await c.req.json().catch(() => null)
  const parsed = SyncQueueRetryRequestSchema.safeParse(body)
  if (!parsed.success) {
    return c.json({ error: 'Invalid sync-queue retry body', issues: parsed.error.issues }, 400)
  }
  const { key, idempotency_key } = parsed.data

  // Same idempotency_key on the same retry click = dedupe (e.g. user
  // double-clicked Retry Now). A fresh click sends a fresh key and
  // bypasses cache by design.
  const cached = await getCachedDispatchResult(c.env, email, idempotency_key)
  if (cached) {
    return c.json({ ...cached, dispatch_id: idempotency_key } satisfies PlaceBetResponse, 200)
  }

  const scan_date = await getLatestScanDate(c.env)
  const existingState = await readState(c.env, email, scan_date)
  const prior = findSyncQueueEntry(existingState, key)
  const attempt_count = (prior?.attempt_count ?? 0) + 1

  const { data } = await loadDataJson(c.env)
  const pickIndex = findPickIndexByKey(data.picks, key)

  if (pickIndex < 0) {
    const entry: SyncQueueEntry = SyncQueueEntrySchema.parse({
      key,
      last_attempt_at: new Date().toISOString(),
      attempt_count,
      last_error: 'Pick no longer in current scan',
      idempotency_key,
    })
    await upsertSyncQueueEntry(c.env, email, scan_date, entry)
    return c.json({ error: 'Pick not found in current scan', key }, 404)
  }

  const result = await dispatchPlaceBet(c.env, [pickIndex], 'v2-sync-retry')
  const enriched: PlaceBetResponse = { ...result, dispatch_id: idempotency_key }
  await cacheDispatchResult(c.env, email, idempotency_key, enriched)

  const entry: SyncQueueEntry = SyncQueueEntrySchema.parse({
    key,
    last_attempt_at: new Date().toISOString(),
    attempt_count,
    last_error: result.status === 'ok' ? null : (result.error ?? 'Dispatch failed'),
    idempotency_key,
  })
  await upsertSyncQueueEntry(c.env, email, scan_date, entry)

  return c.json(enriched, result.status === 'ok' ? 202 : 502)
})

export default app
