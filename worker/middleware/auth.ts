import { createMiddleware } from 'hono/factory'
import type { Env, Variables } from '../env'

export const requireAuth = createMiddleware<{
  Bindings: Env
  Variables: Variables
}>(async (c, next) => {
  const email = c.req.header('cf-access-authenticated-user-email')?.toLowerCase()
  if (!email) return c.text('Unauthorized', 401)
  c.set('email', email)
  await next()
})
