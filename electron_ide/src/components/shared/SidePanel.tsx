import React from 'react'
import { useStore } from '../../stores/ide-store'
import MindGrid from '../analysis_mode/MindGrid'
import Dashboard from '../analysis_mode/Dashboard'
import MemoryLibrary from '../analysis_mode/MemoryLibrary'

export default function SidePanel() {
  const activePanel = useStore((s) => s.activePanel)
  const setActivePanel = useStore((s) => s.setActivePanel)
  const toggleSidebar = useStore((s) => s.toggleSidebar)

  return (
    <aside style={{
      width: 360, borderLeft: '1px solid var(--border)',
      background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column',
    }}>
      {/* Tab 切换 */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {[
          { id: 'mindgrid' as const, label: '心智网格', icon: '◇' },
          { id: 'dashboard' as const, label: '仪表盘', icon: '◆' },
          { id: 'memory' as const, label: '记忆库', icon: '□' },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActivePanel(tab.id)}
            style={{
              flex: 1, padding: '8px 4px', border: 'none', cursor: 'pointer',
              background: activePanel === tab.id ? 'var(--bg-primary)' : 'var(--bg-secondary)',
              color: activePanel === tab.id ? 'var(--accent)' : 'var(--text-muted)',
              fontSize: 11, fontWeight: activePanel === tab.id ? 600 : 400,
              borderBottom: activePanel === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
              transition: 'all 0.12s',
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
        <button onClick={toggleSidebar} style={{
          padding: '8px 10px', border: 'none', cursor: 'pointer',
          color: 'var(--text-muted)', fontSize: 14,
          background: 'transparent',
        }}>
          ✕
        </button>
      </div>

      {/* 面板内容 */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {activePanel === 'mindgrid' && <MindGrid />}
        {activePanel === 'dashboard' && <Dashboard />}
        {activePanel === 'memory' && <MemoryLibrary />}
      </div>
    </aside>
  )
}
