import React, { useState } from 'react'

export default function MemoryLibrary() {
  const [searchQuery, setSearchQuery] = useState('')

  return (
    <div style={{ padding: 12, overflow: 'auto' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
        叙事记忆库
      </div>

      {/* 搜索 */}
      <div style={{ marginBottom: 12 }}>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索角色、事件、地点…"
          style={{
            width: '100%', padding: '6px 10px', border: '1px solid var(--border)',
            borderRadius: 'var(--radius)', fontSize: 12, outline: 'none',
            background: 'var(--bg-primary)',
          }}
        />
      </div>

      {/* 占位内容 */}
      <div style={{
        padding: 12, background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', marginBottom: 8,
      }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>时间线</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          连接引擎后将在此处显示章节时间线
        </div>
      </div>

      <div style={{
        padding: 12, background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', marginBottom: 8,
      }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>未闭合线索</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
          需要导入NSEF种子来激活
        </div>
      </div>
    </div>
  )
}
