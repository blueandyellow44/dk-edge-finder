import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function Header({ scan, bankroll, picksCount }) {
  const { user, profile, signOut } = useAuth()
  const profit = bankroll ? bankroll.current_bankroll - bankroll.starting_bankroll : 0
  const profitColor = profit >= 0 ? 'text-dk-green' : 'text-dk-red'
  const profitSign = profit >= 0 ? '+' : ''

  return (
    <div className="flex justify-between items-start flex-wrap gap-4 mb-6 pb-5 border-b border-border">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">DK Edge Finder</h1>
          {user && (
            <div className="flex items-center gap-2">
              <Link to="/settings" className="text-xs text-muted hover:text-accent">Settings</Link>
              <button onClick={signOut} className="text-xs text-muted hover:text-dk-red">Sign Out</button>
            </div>
          )}
          {!user && (
            <Link to="/login" className="text-xs text-accent hover:underline">Sign In</Link>
          )}
        </div>
        <div className="text-muted text-sm">{scan?.subtitle || 'Loading...'}</div>
        {profile && <div className="text-muted text-xs mt-1">Welcome, {profile.display_name}</div>}
        <div className="inline-flex items-center gap-1.5 text-xs text-muted mt-1">
          <span className="w-2 h-2 rounded-full bg-dk-green animate-pulse" />
          Last scan: {scan?.scan_date || '...'}
        </div>
      </div>

      <div className="flex gap-3 flex-wrap">
        {bankroll && (
          <StatCard label="Bankroll" value={`$${bankroll.current_bankroll.toFixed(2)}`} color="text-dk-blue" />
        )}
        <StatCard label="Games Analyzed" value={scan?.games_analyzed ?? '—'} color="text-accent" />
        <StatCard label="Live Edges" value={picksCount ?? 0} color="text-dk-green" />
        {bankroll && (
          <StatCard label="Lifetime P/L" value={`${profitSign}$${Math.abs(profit).toFixed(2)}`} color={profitColor} />
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-card border border-border rounded-xl px-5 py-3.5 min-w-[130px] text-center">
      <div className="text-[0.7rem] text-muted uppercase tracking-wider">{label}</div>
      <div className={`text-xl font-bold mt-0.5 ${color}`}>{value}</div>
    </div>
  )
}
