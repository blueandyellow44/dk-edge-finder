// In dev (vite + miniflare) the Worker has no Cloudflare Access in front,
// so we inject the canonical email header to match what Access would set
// in production. import.meta.env.DEV is erased to `false` in production
// builds, so this object becomes empty there.
const devHeaders: Record<string, string> = import.meta.env.DEV
  ? { 'cf-access-authenticated-user-email': 'max.sheahan@icloud.com' }
  : {}

export class ApiError extends Error {
  status: number
  body: string
  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`)
    this.status = status
    this.body = body
  }
}

// redirect:'manual' makes Cloudflare Access 302s land as opaqueredirect, not a CORS failure that silently drops bets.
export class AuthRedirectError extends ApiError {
  constructor() {
    super(0, 'sign in required (Cloudflare Access redirected)')
    this.name = 'AuthRedirectError'
  }
}

function checkAuthRedirect(res: Response) {
  if (res.type === 'opaqueredirect') throw new AuthRedirectError()
}

async function unwrap<T>(res: Response): Promise<T> {
  checkAuthRedirect(res)
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return (await res.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(path, {
    credentials: 'same-origin',
    redirect: 'manual',
    headers: { Accept: 'application/json', ...devHeaders },
  }).then((res) => unwrap<T>(res))
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    redirect: 'manual',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...devHeaders,
    },
    body: JSON.stringify(body),
  }).then((res) => unwrap<T>(res))
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(path, {
    method: 'DELETE',
    credentials: 'same-origin',
    redirect: 'manual',
    headers: { ...devHeaders },
  })
  checkAuthRedirect(res)
  if (!res.ok) throw new ApiError(res.status, await res.text())
}
