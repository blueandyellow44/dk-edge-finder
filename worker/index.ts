import { Hono } from 'hono'
import type { Env, Variables } from './env'
import healthApp from './routes/health'
import placeBetsLegacyApp from './routes/place-bets-legacy'
import meApp from './routes/me'
import picksApp from './routes/picks'
import bankrollApp from './routes/bankroll'
import stateApp from './routes/state'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

// Legacy routes mount first so the live single-file index.html can keep
// hitting /api/place-bets without an Access header until cohabitation in step 9.
app.route('/api/health', healthApp)
app.route('/api/place-bets', placeBetsLegacyApp)

// v2 read routes. Each app mounts requireAuth on its own '*' so legacy
// paths above stay public until Cloudflare Access goes live in step 8.
app.route('/api/me', meApp)
app.route('/api/picks', picksApp)
app.route('/api/bankroll', bankrollApp)
app.route('/api/state', stateApp)

app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))

export default app
