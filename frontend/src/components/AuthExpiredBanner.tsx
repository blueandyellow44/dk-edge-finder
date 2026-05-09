import { useSyncExternalStore } from 'react'
import { getAuthExpired, subscribeAuthExpired } from '../lib/authExpired'

export function AuthExpiredBanner() {
  const expired = useSyncExternalStore(subscribeAuthExpired, getAuthExpired)
  if (!expired) return null
  return (
    <div className="auth-expired-banner" role="alert">
      <span>
        <strong>Session expired.</strong> Recent actions may not have saved.
      </span>
      <button onClick={() => window.location.reload()}>Reload to sign in</button>
    </div>
  )
}
