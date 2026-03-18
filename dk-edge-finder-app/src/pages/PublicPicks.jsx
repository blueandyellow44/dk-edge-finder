import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { collection, doc, getDoc, getDocs, query, orderBy, limit } from 'firebase/firestore'
import { db } from '../lib/firebase'
import AlertBanner from '../components/AlertBanner'
import PicksTable from '../components/PicksTable'
import Footer from '../components/Footer'

export default function PublicPicks() {
  const [scan, setScan] = useState(null)
  const [picks, setPicks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchPicks() {
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
      setLoading(false)
    }
    fetchPicks()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-bg text-primary flex items-center justify-center">
        <div className="text-muted">Loading picks...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg text-primary p-6 max-w-[1200px] mx-auto">
      <div className="flex justify-between items-start flex-wrap gap-4 mb-6 pb-5 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold">DK Edge Finder</h1>
          <div className="text-muted text-sm">{scan?.subtitle || 'No scan available'}</div>
          <div className="inline-flex items-center gap-1.5 text-xs text-muted mt-1">
            <span className="w-2 h-2 rounded-full bg-dk-green animate-pulse" />
            Last scan: {scan?.scan_date || '...'}
          </div>
        </div>
        <div className="flex gap-3 flex-wrap">
          <div className="bg-card border border-border rounded-xl px-5 py-3.5 min-w-[130px] text-center">
            <div className="text-[0.7rem] text-muted uppercase tracking-wider">Games Analyzed</div>
            <div className="text-xl font-bold mt-0.5 text-accent">{scan?.games_analyzed ?? '—'}</div>
          </div>
          <div className="bg-card border border-border rounded-xl px-5 py-3.5 min-w-[130px] text-center">
            <div className="text-[0.7rem] text-muted uppercase tracking-wider">Live Edges</div>
            <div className="text-xl font-bold mt-0.5 text-dk-green">{picks.length}</div>
          </div>
        </div>
      </div>

      <AlertBanner scan={scan} picksCount={picks.length} />
      <PicksTable picks={picks} bankroll={null} onBetLogged={() => {}} isPublic />

      <div className="text-center mt-8 p-6 bg-card border border-border rounded-xl">
        <p className="text-muted mb-3">Want personalized Kelly sizing and bet tracking?</p>
        <Link
          to="/login"
          className="inline-block bg-accent text-white px-6 py-2.5 rounded-lg font-semibold hover:bg-accent/80 transition-colors"
        >
          Create Free Account
        </Link>
      </div>

      <Footer />
    </div>
  )
}
