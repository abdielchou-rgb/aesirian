import React from 'react'
import { useStore } from '../../stores/ide-store'

export default function ModeToggle() {
  const mode = useStore((s) => s.mode)
  const setMode = useStore((s) => s.setMode)

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', gap: 0,
      padding: '8px 16px', borderBottom: '1px solid var(--border)',
      background: 'var(--bg-card)', flexShrink: 0,
    }}>
      <button onClick={() => setMode('flow')} style={{
        padding: '6px 20px', border: '1px solid var(--border)',
        borderRadius: '6px 0 0 6px', cursor: 'pointer',
        background: mode === 'flow' ? 'var(--accent)' : 'var(--bg-card)',
        color: mode === 'flow' ? '#fff' : 'var(--text-secondary)',
        fontSize: 12, fontWeight: 500, transition: 'all 0.15s',
      }}>
        ⚡ 心流模式
      </button>
      <button onClick={() => setMode('analysis')} style={{
        padding: '6px 20px', border: '1px solid var(--border)',
        borderRadius: '0 6px 6px 0', cursor: 'pointer',
        background: mode === 'analysis' ? 'var(--accent)' : 'var(--bg-card)',
        color: mode === 'analysis' ? '#fff' : 'var(--text-secondary)',
        fontSize: 12, fontWeight: 500, transition: 'all 0.15s',
      }}>
        🔍 分析模式
      </button>
    </div>
  )
}
