import { useState } from 'react'
import { collection, addDoc, serverTimestamp } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { kellyBetSize } from '../lib/kelly'
import { toDecimalOdds } from '../lib/odds'
import { useAuth } from '../contexts/AuthContext'

export default function LogBetModal({ pick, bankroll, onClose, onBetLogged }) {
  const { user } = useAuth()
  const kelly = kellyBetSize(pick.edge_pct, pick.odds, pick.tier, bankroll.current_bankroll)
  const [wager, setWager] = useState(kelly.betSize.toFixed(2))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)

    const wagerNum = parseFloat(wager)
    if (isNaN(wagerNum) || wagerNum <= 0) {
      setError('Enter a valid wager amount')
      setSaving(false)
      return
    }

    if (wagerNum > bankroll.current_bankroll * 0.05) {
      const proceed = window.confirm(
        `$${wagerNum.toFixed(2)} exceeds 5% of your bankroll ($${(bankroll.current_bankroll * 0.05).toFixed(2)}). Continue anyway?`
      )
      if (!proceed) { setSaving(false); return }
    }

    try {
      await addDoc(collection(db, 'users', user.uid, 'bets'), {
        pick_id: pick.id,
        date: new Date().toISOString().split('T')[0],
        sport: pick.sport,
        event: pick.event,
        pick: pick.pick,
        odds: pick.odds,
        decimal_odds: toDecimalOdds(pick.odds),
        edge_pct: pick.edge_pct,
        tier: pick.tier,
        wager: wagerNum,
        outcome: 'pending',
        pnl: null,
        created_at: serverTimestamp(),
      })

      onBetLogged()
      onClose()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-bold mb-4">Log Bet</h3>
        <div className="space-y-2 text-sm text-muted mb-4">
          <div><strong className="text-primary">{pick.pick}</strong> — {pick.event}</div>
          <div>Odds: <span className="font-mono">{pick.odds}</span> | Edge: +{pick.edge_pct}% | Tier: {pick.tier}</div>
          <div>Kelly suggests: <span className="text-dk-green font-semibold">${kelly.betSize.toFixed(2)}</span></div>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="block text-sm text-muted mb-1">Wager Amount ($)</label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            value={wager}
            onChange={e => setWager(e.target.value)}
            className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-primary font-mono mb-4 focus:outline-none focus:border-accent"
          />

          {error && <div className="text-dk-red text-sm mb-3">{error}</div>}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 bg-accent text-white py-2 rounded-lg font-semibold hover:bg-accent/80 transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Confirm Bet'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border rounded-lg text-muted hover:text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
