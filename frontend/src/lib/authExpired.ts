let expired = false
const listeners = new Set<() => void>()

export function markAuthExpired() {
  if (expired) return
  expired = true
  listeners.forEach((fn) => fn())
}

export function subscribeAuthExpired(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getAuthExpired() {
  return expired
}
