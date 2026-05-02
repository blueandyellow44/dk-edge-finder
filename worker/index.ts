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

export default app
