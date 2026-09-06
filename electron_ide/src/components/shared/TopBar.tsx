import React from 'react'
import { useStore } from '../../stores/ide-store'

export default function TopBar() {
  const project = useStore((s) => s.project)
  const backendConnected = useStore((s) => s.backendConnected)

  return (
    <header style={{
      height: 40, display: 'flex', alignItems: 'center', gap: 16,
      padding: '0 16px', borderBottom: '1px solid var(--border)',
      background: 'var(--bg-card)', flexShrink: 0,
    }}>
      <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--accent)' }}>Æsirian</span>

      {project && (
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginLeft: 16, fontSize: 13, color: 'var(--text-secondary)' }}>
          <span>{project.title}</span>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span>第{project.current_chapter}章</span>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span style={{
            background: 'var(--bg-secondary)', padding: '1px 8px', borderRadius: 4,
            fontSize: 11
          }}>{project.genre}</span>
        </div>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: backendConnected ? 'var(--pass)' : 'var(--danger)',
        }} />
        <span style={{ color: 'var(--text-muted)' }}>
          {backendConnected ? '引擎连线中' : '本地模式'}
        </span>
      </div>
    </header>
  )
}
