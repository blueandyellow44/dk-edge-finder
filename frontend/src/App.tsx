import { useState } from 'react'
import { Header } from './components/Header'
import { TabBar } from './components/TabBar'
import { BalanceCard } from './components/BalanceCard'
import { PicksTab } from './tabs/PicksTab'
import { PendingTab } from './tabs/PendingTab'
import { ActivityTab } from './tabs/ActivityTab'
import { PositionsTab } from './tabs/PositionsTab'
import { AccountTab } from './tabs/AccountTab'
import { useMe } from './api/queries'

export type TabId = 'picks' | 'pending' | 'activity' | 'positions' | 'account'

const TABS: { id: TabId; label: string }[] = [
  { id: 'picks', label: 'Picks' },
  { id: 'pending', label: 'Pending' },
  { id: 'activity', label: 'Activity' },
  { id: 'positions', label: 'Positions' },
  { id: 'account', label: 'Account' },
]

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('picks')
  const me = useMe()

  return (
    <div className="app">
      <Header email={me.data?.email} pictureUrl={me.data?.picture_url ?? null} />
      <main className="page">
        <div className="page-main">
          <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />
          <section className="tab-panel">
            {activeTab === 'picks' && <PicksTab />}
            {activeTab === 'pending' && <PendingTab />}
            {activeTab === 'activity' && <ActivityTab />}
            {activeTab === 'positions' && <PositionsTab />}
            {activeTab === 'account' && <AccountTab />}
          </section>
        </div>
        <aside className="page-side">
          <BalanceCard />
        </aside>
      </main>
    </div>
  )
}

export default App
