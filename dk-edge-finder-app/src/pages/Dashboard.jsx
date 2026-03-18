import { useEffect, useState, useCallback } from 'react'
import { collection, doc, getDoc, getDocs, query, orderBy, limit } from 'firebase/firestore'
import { db } from '../lib/firebase'
import { useAuth } from '../contexts/AuthContext'
import Header from '../components/Header'
import AlertBanner from '../components/AlertBanner'
import PicksTable from '../components/PicksTable'
import BankrollCards from '../components/BankrollCards'
import BetHistory from '../components/BetHistory'
import Footer from '../components/Footer'

export default function Dashboard() {
  const { user } = useAuth()
  const [scan, setScan] = useState(null)
  const [picks, setPicks] = useState([])
  const [bankroll, setBankroll] = useState(null)
  const [bets, setBets] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    // Fetch most recent scan — try today first, then get latest
    const today = new Date().toISOString().split('T')[0]
    let scanData = null
    let scanId = null

    const todaySnap = await getDoc(doc(db, 'daily_scans', today))
    if (todaySnap.exists()) {
      scanData = { id: todaySnap.id, ...todaySnap.data() }
      scanId = todaySnap.id
    } else {
      const scansQuery = query(
        collection(db, 'daily_scans'),
        orderBy('scan_date', 'desc'),
        limit(1)
      )
      const scansSnap = await getDocs(scansQuery)
      if (!scansSnap.empty) {
        const latestDoc = scansSnap.docs[0]
        scanData = { id: latestDoc.id, ...latestDoc.data() }
        scanId = latestDoc.id
      }
    }
    setScan(scanData)

    // Fetch picks for that scan (subcollection)
    if (scanId) {
      const picksSnap = await getDocs(
        query(collection(db, 'daily_scans', scanId, 'picks'), orderBy('rank'))
      )
      const now = new Date()
      const picksData = picksSnap.docs
        .map(d => ({ id: d.id, ...d.data() }))
        .filter(p => !p.game_time || p.game_time.toDate() > now)
      setPicks(picksData)
    }

    // Fetch user bankroll (embedded in user doc)
    const userSnap = await getDoc(doc(db, 'users', user.uid))
    if (userSnap.exists()) {
      const userData = userSnap.data()
      setBankroll({
        current_bankroll: userData.bankroll?.current ?? 500,
        starting_bankroll: userData.bankroll?.starting ?? 500,
        last_updated: userData.bankroll?.last_updated,
        user_id: user.uid,
      })
    }

    // Fetch user bets (subcollection)
    const betsSnap = await getDocs(
      query(collection(db, 'users', user.uid, 'bets'), orderBy('date', 'desc'))
    )
    setBets(betsSnap.docs.map(d => ({ id: d.id, ...d.data() })))

    setLoading(false)
  }, [user.uid])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) {
    return (
      <div className="min-h-screen bg-bg text-primary flex items-center justify-center">
        <div className="text-muted">Loading dashboard...</div>
      </div>
    )
  }

  const stats = bets.reduce(
    (acc, b) => {
      if (b.outcome === 'win') acc.wins++
      else if (b.outcome === 'loss') acc.losses++
      else if (b.outcome === 'push') acc.pushes++
      return acc
    },
    { wins: 0, losses: 0, pushes: 0 }
  )

  const today = new Date().toISOString().split('T')[0]
  const todayWagers = bets
    .filter(b => b.date === today && b.outcome === 'pending')
    .map(b => b.wager)

  const pendingBets = bets.filter(b => b.outcome === 'pending')

  const scanIsStale = scan && scan.scan_date === today && scan.created_at &&
    (Date.now() - (scan.created_at.toDate ? scan.created_at.toDate() : new Date(scan.created_at)).getTime()) > 2 * 60 * 60 * 1000

  return (
    <div className="min-h-screen bg-bg text-primary p-6 max-w-[1200px] mx-auto">
      <Header scan={scan} bankroll={bankroll} picksCount={picks.length} />

      {scanIsStale && (
        <div className="bg-dk-orange/10 border border-dk-orange rounded-xl p-3 px-4 mb-4 text-dk-orange text-sm">
          Odds data may be stale (scan is over 2 hours old). Lines may have moved.
        </div>
      )}

      <AlertBanner scan={scan} picksCount={picks.length} />
      <PicksTable picks={picks} bankroll={bankroll} onBetLogged={fetchData} />
      <BankrollCards bankroll={bankroll} stats={stats} todayWagers={todayWagers} pendingBets={pendingBets} />
      <BetHistory bets={bets} bankroll={bankroll} onBetResolved={fetchData} />
      <Footer />
    </div>
  )
}
