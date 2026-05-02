import { usePicks, useStateRecord } from '../api/queries'
import { usePlacePickBet, useSkipPick } from '../api/mutations'
import { PositionRow } from '../components/PositionRow'
import type { Pick, Placement } from '../../../shared/types'

const placementKey = (pick: Pick) => `${pick.pick}|${pick.event}`

export function PositionsTab() {
  const picks = usePicks()
  const state = useStateRecord()
  const placeMutation = usePlacePickBet()
  const skipMutation = useSkipPick()

  if (picks.isLoading) {
    return <div className="placeholder">Loading positions...</div>
  }
  if (picks.isError || !picks.data) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">Failed to load positions</div>
        <p>The /api/picks endpoint did not respond.</p>
      </div>
    )
  }

  const { picks: pickList } = picks.data
  if (pickList.length === 0) {
    return (
      <div className="placeholder">
        <div className="placeholder-title">No positions today</div>
        <p>The latest scan found no profitable bets.</p>
      </div>
    )
  }

  const placementByKey = new Map<string, Placement>()
  for (const p of state.data?.placements ?? []) placementByKey.set(p.key, p)
  const isPending = placeMutation.isPending || skipMutation.isPending

  return (
    <div className="position-list">
      {pickList.map((pick, index) => {
        const key = placementKey(pick)
        return (
          <PositionRow
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
  )
}
