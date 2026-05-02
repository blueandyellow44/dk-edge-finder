import type { Env } from '../env'
import {
  StateRecordSchema,
  PlacementSchema,
  ManualBetSchema,
  BalanceOverrideRecordSchema,
} from '../../shared/schemas'
import type {
  StateRecord,
  Placement,
  ManualBet,
  BalanceOverrideRecord,
} from '../../shared/types'

function stateKey(email: string, scan_date: string): string {
  return `state:${email}:${scan_date}`
}

function balanceOverrideKey(email: string): string {
  return `balance_override:${email}`
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

export async function removeManualBet(
  env: Env,
  email: string,
  scan_date: string,
  id: string,
): Promise<{ removed: boolean; record: StateRecord | null }> {
  const record = await readState(env, email, scan_date)
  if (!record) return { removed: false, record: null }
  const before = record.manual_bets.length
  record.manual_bets = record.manual_bets.filter((b) => b.id !== id)
  if (record.manual_bets.length === before) return { removed: false, record }
  record.updated_at = new Date().toISOString()
  await writeState(env, record)
  return { removed: true, record }
}

export async function getBalanceOverride(
  env: Env,
  email: string,
): Promise<BalanceOverrideRecord | null> {
  const raw = await env.EDGE_STATE.get(balanceOverrideKey(email))
  if (!raw) return null
  try {
    return BalanceOverrideRecordSchema.parse(JSON.parse(raw))
  } catch {
    return null
  }
}

export async function upsertBalanceOverride(
  env: Env,
  email: string,
  amount: number,
  note: string,
): Promise<BalanceOverrideRecord> {
  const record: BalanceOverrideRecord = {
    schema_version: 1,
    email,
    amount,
    note,
    updated_at: new Date().toISOString(),
  }
  const validated = BalanceOverrideRecordSchema.parse(record)
  await env.EDGE_STATE.put(balanceOverrideKey(email), JSON.stringify(validated))
  return validated
}
