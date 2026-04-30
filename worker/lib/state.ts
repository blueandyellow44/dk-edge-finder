import type { Env } from '../env'
import {
  StateRecordSchema,
  PlacementSchema,
  ManualBetSchema,
  SyncQueueEntrySchema,
} from '../../shared/schemas'
import type {
  StateRecord,
  Placement,
  ManualBet,
  SyncQueueEntry,
} from '../../shared/types'

function stateKey(email: string, scan_date: string): string {
  return `state:${email}:${scan_date}`
}

function emptyRecord(email: string, scan_date: string): StateRecord {
  return {
    schema_version: 1,
    email,
    scan_date,
    placements: [],
    sync_queue: [],
    manual_bets: [],
    updated_at: new Date().toISOString(),
  }
}

export async function readState(env: Env, email: string, scan_date: string): Promise<StateRecord | null> {
  const raw = await env.EDGE_STATE.get(stateKey(email, scan_date))
  if (!raw) return null
  try {
    return StateRecordSchema.parse(JSON.parse(raw))
  } catch {
    return null
  }
}

export async function writeState(env: Env, record: StateRecord): Promise<void> {
  const validated = StateRecordSchema.parse(record)
  await env.EDGE_STATE.put(stateKey(validated.email, validated.scan_date), JSON.stringify(validated))
}

async function readOrInit(env: Env, email: string, scan_date: string): Promise<StateRecord> {
  const existing = await readState(env, email, scan_date)
  return existing ?? emptyRecord(email, scan_date)
}

export async function appendPlacement(
  env: Env,
  email: string,
  scan_date: string,
  p: Placement,
): Promise<StateRecord> {
  const placement = PlacementSchema.parse(p)
  const record = await readOrInit(env, email, scan_date)
  const exists = record.placements.some((existing) => existing.idempotency_key === placement.idempotency_key)
  if (!exists) record.placements.push(placement)
  record.updated_at = new Date().toISOString()
  await writeState(env, record)
  return record
}

export async function appendManualBet(
  env: Env,
  email: string,
  scan_date: string,
  b: ManualBet,
): Promise<StateRecord> {
  const bet = ManualBetSchema.parse(b)
  const record = await readOrInit(env, email, scan_date)
  const exists = record.manual_bets.some((existing) => existing.idempotency_key === bet.idempotency_key)
  if (!exists) record.manual_bets.push(bet)
  record.updated_at = new Date().toISOString()
  await writeState(env, record)
  return record
}

export async function upsertSyncQueueEntry(
  env: Env,
  email: string,
  scan_date: string,
  entry: SyncQueueEntry,
): Promise<StateRecord> {
  const validated = SyncQueueEntrySchema.parse(entry)
  const record = await readOrInit(env, email, scan_date)
  const idx = record.sync_queue.findIndex((e) => e.idempotency_key === validated.idempotency_key)
  if (idx >= 0) record.sync_queue[idx] = validated
  else record.sync_queue.push(validated)
  record.updated_at = new Date().toISOString()
  await writeState(env, record)
  return record
}
