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

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(res.status, await res.text())
  return (await res.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return fetch(path, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...devHeaders },
  }).then((res) => unwrap<T>(res))
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
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
    headers: { ...devHeaders },
  })
  if (!res.ok) throw new ApiError(res.status, await res.text())
}
