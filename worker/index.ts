import { Hono } from 'hono'
import type { Env } from './env'
import healthApp from './routes/health'
import placeBetsLegacyApp from './routes/place-bets-legacy'

const app = new Hono<{ Bindings: Env }>()

app.route('/api/health', healthApp)
app.route('/api/place-bets', placeBetsLegacyApp)

app.all('*', (c) => c.env.ASSETS.fetch(c.req.raw))

export default app
