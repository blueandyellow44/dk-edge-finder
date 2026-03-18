export default function AlertBanner({ scan, picksCount }) {
  if (picksCount > 0 && scan?.best_bet_title) {
    return (
      <div className="bg-gradient-to-r from-accent/15 to-dk-blue/15 border border-accent rounded-xl p-4 px-5 mb-6 flex items-center gap-3">
        <div className="text-2xl">&#9889;</div>
        <div className="flex-1">
          <div className="font-semibold text-[0.95rem]">Best Bet: {scan.best_bet_title}</div>
          <div className="text-muted text-sm">{scan.best_bet_desc}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gradient-to-r from-dk-yellow/10 to-dk-orange/10 border border-dk-yellow rounded-xl p-4 px-5 mb-6 flex items-center gap-3">
      <div className="text-2xl">&#128522;</div>
      <div className="flex-1">
        <div className="font-semibold text-[0.95rem]">No edges today</div>
        <div className="text-muted text-sm">All lines look fairly priced. Patience is edge.</div>
      </div>
    </div>
  )
}
