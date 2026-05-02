import type { TabId } from '../App'

type TabBarProps = {
  tabs: { id: TabId; label: string }[]
  active: TabId
  onChange: (id: TabId) => void
}

export function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <nav className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={active === t.id}
          className={`tab ${active === t.id ? 'active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
