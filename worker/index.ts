import { Hono } from 'hono'
import type { Env, Variables } from './env'
import healthApp from './routes/health'
import meApp from './routes/me'
import picksApp from './routes/picks'
import bankrollApp from './routes/bankroll'
import stateApp from './routes/state'
import statePlacementsApp from './routes/state-placements'
import stateManualBetsApp from './routes/state-manual-bets'
import balanceOverrideApp from './routes/balance-override'
import activityApp from './routes/activity'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.route('/api/health', healthApp)

// v2 routes. Mount more-specific /api/state/* sub-paths BEFORE the
// generic /api/state router so the latter's wildcard middleware never
// gets a chance to swallow the sub-path requests.
app.route('/api/me', meApp)
app.route('/api/picks', picksApp)
app.route('/api/bankroll', bankrollApp)

app.route('/api/state/placements', statePlacementsApp)
app.route('/api/state/manual-bets', stateManualBetsApp)
app.route('/api/state', stateApp)

app.route('/api/balance-override', balanceOverrideApp)
app.route('/api/activity', activityApp)

app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))

// ──────────── Scheduled handler: backup Full Scan dispatcher ────────────
//
// GitHub Actions cron schedules are unreliable under high load — they
// commonly fire 1-3 hours late and occasionally skip a day entirely
// (2026-05-12 was a complete miss for the 13:00 UTC Full Scan). Cloudflare
// Cron Triggers carry a real SLA, so we lean on the Worker's own
// scheduler as a safety net: fire at 15:00 UTC (two hours after the GH
// schedule, generous slack for late-firing crons), check whether
// data.json's scan_date already shows today, and dispatch the Full Scan
// workflow only if today's data is missing.
//
// Idempotency comes from the data.json freshness check — if GH Actions
// did fire on time, the worker no-ops and burns no Odds API credits. On
// a real skip, the worker dispatches and the workflow runs once,
// covered by the existing concurrency: dk-data-write group so two
// near-simultaneous triggers serialize rather than parallel-scan.

const REPO = 'blueandyellow44/dk-edge-finder'
const FULL_SCAN_WORKFLOW_FILE = 'morning-scan.yml'

async function todayHasFreshScan(env: Env): Promise<boolean> {
  try {
    const res = await env.ASSETS.fetch(new Request('https://assets.local/data.json'))
    if (!res.ok) return false
    const data = (await res.json()) as { scan_date?: unknown }
    if (typeof data.scan_date !== 'string') return false
    const today = new Date().toISOString().slice(0, 10)
    return data.scan_date === today
  } catch {
    return false
  }
}

async function dispatchFullScan(env: Env): Promise<void> {
  if (!env.GITHUB_TOKEN) {
    console.error('cron-bridge: GITHUB_TOKEN missing; cannot dispatch Full Scan')
    return
  }
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${FULL_SCAN_WORKFLOW_FILE}/dispatches`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'dk-edge-finder-cron-bridge',
    },
    body: JSON.stringify({ ref: 'main' }),
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    console.error(
      `cron-bridge: Full Scan dispatch failed ${res.status}: ${body.slice(0, 200)}`,
    )
    return
  }
  console.log('cron-bridge: Full Scan workflow dispatched')
}

export default {
  fetch: app.fetch,
  async scheduled(_event: ScheduledController, env: Env, ctx: ExecutionContext) {
    if (await todayHasFreshScan(env)) {
      console.log('cron-bridge: data.json scan_date matches today, no dispatch')
      return
    }
    ctx.waitUntil(dispatchFullScan(env))
  },
} satisfies ExportedHandler<Env>
