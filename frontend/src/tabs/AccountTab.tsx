import { useBankroll, useMe } from '../api/queries'
import { BalanceOverrideForm } from '../components/BalanceOverrideForm'
import { formatPercent, formatSignedMoney } from '../lib/format'

export function AccountTab() {
  const me = useMe()
  const bankroll = useBankroll()

  if (me.isLoading || bankroll.isLoading) {
    return <div className="placeholder">Loading account...</div>
  }
  if (me.isError || bankroll.isError || !me.data || !bankroll.data) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Failed to load account</div>
        <p>The /api/me or /api/bankroll endpoint did not respond.</p>
      </div>
    )
  }

  const { email, picture_url } = me.data
  const { lifetime, balance_override } = bankroll.data
  const initial = email[0].toUpperCase()
  const profitClass =
    lifetime.profit > 0 ? 'positive' : lifetime.profit < 0 ? 'negative' : ''
  const roiClass =
    lifetime.roi_pct > 0 ? 'positive' : lifetime.roi_pct < 0 ? 'negative' : ''

  return (
    <>
      <div className="account-section">
        <div className="account-section-title">Identity</div>
        <div className="identity-row">
          <span className="identity-avatar" aria-hidden="true">
            {picture_url ? <img src={picture_url} alt="" /> : initial}
          </span>
          <div className="identity-info">
            <div className="identity-email">{email}</div>
            <div className="identity-sub">Signed in via Cloudflare Access</div>
          </div>
          <a className="btn btn-outline btn-sm" href="/cdn-cgi/access/logout">
            Sign out
          </a>
        </div>
      </div>

      <div className="account-section">
        <div className="account-section-title">Balance override</div>
        <BalanceOverrideForm current={balance_override} />
      </div>

      <div className="account-section">
        <div className="account-section-title">Lifetime stats</div>
        <div className="stats-grid">
          <div className="stat">
            <div className="stat-label">Bets</div>
            <div className="stat-value">{lifetime.bets}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Wins</div>
            <div className="stat-value">{lifetime.wins}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Losses</div>
            <div className="stat-value">{lifetime.losses}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Pushes</div>
            <div className="stat-value">{lifetime.pushes}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Profit</div>
            <div className={`stat-value ${profitClass}`}>
              {formatSignedMoney(lifetime.profit)}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">ROI</div>
            <div className={`stat-value ${roiClass}`}>
              {formatPercent(lifetime.roi_pct)}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
