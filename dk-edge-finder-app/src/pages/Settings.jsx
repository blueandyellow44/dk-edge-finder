import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { doc, updateDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { useAuth } from '../contexts/AuthContext'
import Footer from '../components/Footer'

export default function Settings() {
  const { user, profile, fetchProfile } = useAuth()
  const [displayName, setDisplayName] = useState('')
  const [startingBankroll, setStartingBankroll] = useState('')
  const [currentBankroll, setCurrentBankroll] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name || '')
      setStartingBankroll((profile.bankroll?.starting ?? 500).toString())
      setCurrentBankroll((profile.bankroll?.current ?? 500).toString())
    }
  }, [profile])

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    const startVal = parseFloat(startingBankroll)
    const currentVal = parseFloat(currentBankroll)
    if (isNaN(startVal) || isNaN(currentVal) || startVal < 0 || currentVal < 0) {
      setMessage({ type: 'error', text: 'Invalid bankroll values' })
      setSaving(false)
      return
    }

    try {
      await updateDoc(doc(db, 'users', user.uid), {
        display_name: displayName.trim(),
        'bankroll.starting': startVal,
        'bankroll.current': currentVal,
        'bankroll.last_updated': serverTimestamp(),
      })

      await fetchProfile(user.uid)
      setMessage({ type: 'success', text: 'Settings saved!' })
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    }
    setSaving(false)
  }

  return (
    <div className="min-h-screen bg-bg text-primary p-6 max-w-lg mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="text-accent hover:underline text-sm">&larr; Dashboard</Link>
        <h1 className="text-2xl font-bold">Settings</h1>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        <div>
          <label className="block text-sm text-muted mb-1">Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            className="input-field"
          />
        </div>

        <div>
          <label className="block text-sm text-muted mb-1">Starting Bankroll ($)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={startingBankroll}
            onChange={e => setStartingBankroll(e.target.value)}
            className="input-field"
          />
          <p className="text-xs text-muted mt-1">Your initial deposit amount for ROI tracking</p>
        </div>

        <div>
          <label className="block text-sm text-muted mb-1">Current Bankroll ($)</label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={currentBankroll}
            onChange={e => setCurrentBankroll(e.target.value)}
            className="input-field"
          />
          <p className="text-xs text-muted mt-1">Sync this with your actual DraftKings account balance</p>
        </div>

        {message && (
          <div className={`text-sm ${message.type === 'error' ? 'text-dk-red' : 'text-dk-green'}`}>
            {message.text}
          </div>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-accent text-white py-2.5 rounded-lg font-semibold hover:bg-accent/80 transition-colors disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </form>

      <div className="mt-8 p-4 bg-card border border-border rounded-xl text-sm text-muted">
        <strong>Account</strong><br />
        Email: {user?.email}<br />
        User ID: <span className="font-mono text-xs">{user?.uid}</span>
      </div>

      <Footer />
    </div>
  )
}
