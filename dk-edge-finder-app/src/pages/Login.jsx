import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Footer from '../components/Footer'

export default function Login() {
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [confirmMsg, setConfirmMsg] = useState(null)

  const { signIn, signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    if (isSignUp) {
      if (!displayName.trim()) { setError('Display name required'); setLoading(false); return }
      const { error: err } = await signUp(email, password, displayName.trim())
      if (err) { setError(err.message); setLoading(false); return }
      setConfirmMsg('Check your email to confirm your account, then sign in.')
      setIsSignUp(false)
    } else {
      const { error: err } = await signIn(email, password)
      if (err) { setError(err.message); setLoading(false); return }
      navigate('/')
    }
    setLoading(false)
  }

  async function handleGoogle() {
    const { error: err } = await signInWithGoogle()
    if (err) setError(err.message)
  }

  return (
    <div className="min-h-screen bg-bg text-primary flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-1">DK Edge Finder</h1>
        <p className="text-muted text-sm text-center mb-6">
          {isSignUp ? 'Create your account' : 'Sign in to your account'}
        </p>

        {confirmMsg && (
          <div className="bg-dk-green/10 border border-dk-green rounded-lg p-3 text-dk-green text-sm mb-4">
            {confirmMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isSignUp && (
            <input
              type="text"
              placeholder="Display Name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="input-field"
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            className="input-field"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            minLength={6}
            className="input-field"
          />

          {error && <div className="text-dk-red text-sm">{error}</div>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent text-white py-2.5 rounded-lg font-semibold hover:bg-accent/80 transition-colors disabled:opacity-50"
          >
            {loading ? 'Please wait...' : isSignUp ? 'Create Account' : 'Sign In'}
          </button>
        </form>

        <div className="flex items-center gap-3 my-4">
          <div className="flex-1 h-px bg-border" />
          <span className="text-muted text-xs">or</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        <button
          onClick={handleGoogle}
          className="w-full border border-border py-2.5 rounded-lg text-primary font-medium hover:bg-card transition-colors"
        >
          Continue with Google
        </button>

        <p className="text-center text-muted text-sm mt-4">
          {isSignUp ? (
            <>Already have an account? <button onClick={() => { setIsSignUp(false); setError(null) }} className="text-accent hover:underline">Sign in</button></>
          ) : (
            <>Need an account? <button onClick={() => { setIsSignUp(true); setError(null) }} className="text-accent hover:underline">Sign up</button></>
          )}
        </p>

        <p className="text-center text-muted text-xs mt-4">
          <a href="/picks" className="text-accent hover:underline">View today's picks without an account</a>
        </p>

        <Footer />
      </div>
    </div>
  )
}
