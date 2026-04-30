import { Hono } from 'hono'
import type { Env, Variables } from '../env'
import { requireAuth } from '../middleware/auth'
import { MeResponseSchema } from '../../shared/schemas'

const app = new Hono<{ Bindings: Env; Variables: Variables }>()

app.use('*', requireAuth)

// Decode the Cloudflare Access JWT payload (middle segment) without
// verifying the signature. Access already guards this route — the JWT
// is read only for non-security claims like Google's picture URL.
function pictureUrlFromJwt(jwt: string | undefined): string | null {
  if (!jwt) return null
  const parts = jwt.split('.')
  if (parts.length < 2) return null
  try {
    const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4)
    const decoded = atob(padded)
    const claims = JSON.parse(decoded) as { picture?: unknown; custom?: { picture?: unknown } }
    const pic =
      typeof claims.picture === 'string'
        ? claims.picture
        : typeof claims.custom?.picture === 'string'
          ? claims.custom.picture
          : null
    return pic
  } catch {
    return null
  }
}

app.get('/', (c) => {
  const email = c.get('email')
  const jwt = c.req.header('cf-access-jwt-assertion')
  const picture_url = pictureUrlFromJwt(jwt)
  return c.json(MeResponseSchema.parse({ email, picture_url }))
})

export default app
