import { usePicks, useStateRecord } from '../api/queries'
import { usePlacePickBet, useSkipPick } from '../api/mutations'
import { PickRow } from '../components/PickRow'
import { formatAgo } from '../lib/format'
import type { Pick, Placement } from '../../../shared/types'

const placementKey = (pick: Pick) => `${pick.pick}|${pick.event}`

export function PicksTab() {
  const picks = usePicks()
  const state = useStateRecord()
  const placeMutation = usePlacePickBet()
  const skipMutation = useSkipPick()

  if (picks.isLoading) {
    return <div className="placeholder">Loading picks...</div>
  }

  if (picks.isError || !picks.data) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Failed to load picks</div>
        <p>The /api/picks endpoint did not respond.</p>
      </div>
    )
  }

  const { scan_subtitle, scan_age_seconds, picks: pickList, no_edge_games } = picks.data
  const placementByKey = new Map<string, Placement>()
  for (const p of state.data?.placements ?? []) {
    placementByKey.set(p.key, p)
  }
  const stale = scan_age_seconds !== null && scan_age_seconds > 12 * 3600
  const ago = formatAgo(scan_age_seconds)
  const isPending = placeMutation.isPending || skipMutation.isPending

  return (
    <>
      <div className={`scan-meta ${stale ? 'stale' : ''}`}>
        <span className="scan-meta-title">{scan_subtitle}</span>
        {ago && <span className="scan-meta-age">{ago}</span>}
      </div>
      {pickList.length === 0 ? (
        <div className="placeholder">
          <div className="placeholder-title">No edges today</div>
          <p>The latest scan found no profitable bets. The next cron tick refreshes data.</p>
        </div>
      ) : (
        <div className="tx-list">
          <div className="tx-header">
            <div>Rank</div>
            <div>Pick / Event</div>
            <div className="pick-odds">Odds</div>
            <div className="pick-edge">Edge</div>
            <div className="pick-wager">Wager</div>
            <div></div>
          </div>
          {pickList.map((pick, index) => {
            const key = placementKey(pick)
            return (
              <PickRow
                key={key}
                pick={pick}
                index={index}
                placement={placementByKey.get(key)}
                isPending={isPending}
                onPlace={() => placeMutation.mutate({ pickIndex: index, key })}
                onSkip={() => skipMutation.mutate({ key })}
              />
            )
          })}
        </div>
      )}
      {no_edge_games.length > 0 && (
        <details className="no-edge">
          <summary className="no-edge-summary">
            No-edge games ({no_edge_games.length})
          </summary>
          {no_edge_games.map((g, i) => (
            <div key={`${g.event}-${i}`} className="no-edge-row">
              <div className="no-edge-event">
                <span className="pick-sport">{g.sport}</span> {g.event}
              </div>
              <div className="no-edge-line">{g.line}</div>
              <div className="no-edge-reason">{g.reason}</div>
            </div>
          ))}
        </details>
      )}
    </>
  )
}
