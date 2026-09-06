import React from 'react'
import { useStore } from '../../stores/ide-store'

export default function Dashboard() {
  const mindGrid = useStore((s) => s.mindGrid)
  const auditReports = useStore((s) => s.auditReports)
  const cooldownHot = mindGrid.tension_points

  return (
    <div style={{ padding: 12, overflow: 'auto' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
        叙事仪表盘
      </div>

      {/* 审计分数 */}
      <div style={{
        padding: 12, background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', marginBottom: 8,
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>总体审计得分</div>
        <div style={{ fontSize: 28, fontWeight: 700 }}>
          {auditReports.length > 0
            ? Math.round(auditReports[auditReports.length - 1].overall_score)
            : '—'}
        </div>
      </div>

      {/* 张力点 */}
      <div style={{
        padding: 12, background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', marginBottom: 8,
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
          未解决的戏剧张力
        </div>
        {cooldownHot.slice(0, 4).map((tp, i) => (
          <div key={i} style={{
            padding: '6px 0', borderBottom: i < cooldownHot.length - 1 ? '1px solid var(--border)' : 'none',
            fontSize: 12, lineHeight: 1.5,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--text-secondary)' }}>{tp.description.slice(0, 50)}</span>
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: tp.intensity > 0.7 ? '#fce8e8' : '#fff3e0',
                color: tp.intensity > 0.7 ? 'var(--danger)' : '#c49000',
                flexShrink: 0, marginLeft: 8,
              }}>
                {Math.round(tp.intensity * 100)}
              </span>
            </div>
          </div>
        ))}
        {cooldownHot.length === 0 && (
          <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>暂无活动张力点</div>
        )}
      </div>

      {/* 传输度 */}
      <div style={{
        padding: 12, background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>叙事传输度趋势</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          等待数据累积…
        </div>
      </div>
    </div>
  )
}
