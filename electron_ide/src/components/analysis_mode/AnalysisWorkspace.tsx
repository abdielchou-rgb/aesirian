import React, { useEffect, useState } from 'react'
import { useStore } from '../../stores/ide-store'

/**
 * 分析模式工作台
 * 写作画布（左）+ 审计批注（旁）+ 假设推演面板（底部）
 */
export default function AnalysisWorkspace() {
  const canvasText = useStore((s) => s.canvasText)
  const setCanvasText = useStore((s) => s.setCanvasText)
  const auditReports = useStore((s) => s.auditReports)
  const setMindGrid = useStore((s) => s.setMindGrid)
  const addAuditReport = useStore((s) => s.addAuditReport)

  const [showHypothetical, setShowHypothetical] = useState(false)

  // 假设推演
  const [beliefChange, setBeliefChange] = useState('')
  const [hypotheticalResult, setHypotheticalResult] = useState('')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* 左边：文本画布 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
            <span>文本区</span>
            {auditReports.length > 0 && (
              <span>· 最近审计: {auditReports[auditReports.length - 1].overall_score}/100</span>
            )}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
              <button
                onClick={() => setShowHypothetical(!showHypothetical)}
                style={{
                  padding: '2px 10px', border: '1px solid var(--border)',
                  borderRadius: 4, background: 'var(--bg-card)', fontSize: 11, cursor: 'pointer',
                  color: 'var(--accent)',
                }}
              >
                假设推演
              </button>
              <button
                onClick={async () => {
                  // 模拟提交章节→审计
                  const fakeReport = {
                    chapter: useStore.getState().project?.current_chapter || 0,
                    overall_score: 87,
                    timestamp: new Date().toISOString(),
                    results: [
                      { gate_id: 'G9', gate_name: '去AI化检测', level: 'WARN' as const, message: '模糊词密度略高', suggestion: '减少"似乎""可能"的使用' },
                      { gate_id: 'G7', gate_name: '叙事节奏', level: 'PASS' as const, message: '节奏良好' },
                    ]
                  }
                  addAuditReport(fakeReport)
                }}
                style={{
                  padding: '2px 10px', border: '1px solid var(--accent)',
                  borderRadius: 4, background: 'var(--accent)', fontSize: 11, cursor: 'pointer',
                  color: '#fff',
                }}
              >
                提交审计
              </button>
            </div>
          </div>
          <textarea
            value={canvasText}
            onChange={(e) => setCanvasText(e.target.value)}
            style={{
              flex: 1, border: 'none', resize: 'none', outline: 'none', padding: '24px 32px',
              fontFamily: 'var(--font-body)', fontSize: 15, lineHeight: 1.9,
              color: 'var(--text-primary)', background: 'transparent',
            }}
          />
        </div>

        {/* 右边：批注面板 */}
        <div style={{ width: 260, overflow: 'auto', flexShrink: 0 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
            审计批注
          </div>
          {auditReports.length === 0 && (
            <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', marginTop: 40 }}>
              提交审计后，批注将在此处显示
            </div>
          )}
          {auditReports.map((report, ri) => (
            <div key={ri} style={{ padding: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
                第{report.chapter}章 · {report.overall_score}/100
              </div>
              {report.results.map((r, i) => (
                <div key={i} style={{
                  padding: '6px 8px', marginBottom: 4,
                  borderRadius: 4, fontSize: 11, lineHeight: 1.5,
                  background: r.level === 'WARN' ? '#fff8f0' : r.level === 'BLOCK' ? '#fef2f2' : '#f5f9f5',
                  borderLeft: `3px solid ${
                    r.level === 'BLOCK' ? 'var(--danger)' :
                    r.level === 'WARN' ? 'var(--warn)' : 'var(--pass)'
                  }`,
                }}>
                  <div style={{ fontWeight: 500, marginBottom: 2 }}>
                    {r.gate_id} {r.gate_name}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>{r.message}</div>
                  {r.suggestion && (
                    <div style={{ color: 'var(--accent)', marginTop: 2, fontSize: 10 }}>
                      {r.suggestion}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* 假设推演面板 */}
      {showHypothetical && (
        <div style={{
          height: 180, borderTop: '1px solid var(--border)',
          background: 'var(--bg-card)', padding: 12, overflow: 'auto',
        }}>
          <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 8, color: 'var(--text-secondary)' }}>
            假设推演 — 改变角色信念，预览故事走向变化
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input
              type="text"
              value={beliefChange}
              onChange={(e) => setBeliefChange(e.target.value)}
              placeholder="例如: 角色A发现B一直在骗自己"
              style={{
                flex: 1, padding: '6px 10px', border: '1px solid var(--border)',
                borderRadius: 'var(--radius)', fontSize: 12, outline: 'none',
              }}
            />
            <button
              onClick={() => {
                setHypotheticalResult(
                  '如果「角色A发现B在骗自己」:\n' +
                  '- 角色A的目标将从"保护B"变为"查明B的身份"\n' +
                  '- 戏剧张力类型变为「递归错位」\n' +
                  '- 建议场景: A不动声色地试探B，B毫无察觉'
                )
              }}
              style={{
                padding: '6px 16px', border: '1px solid var(--accent)',
                borderRadius: 'var(--radius)', background: 'var(--accent)',
                color: '#fff', fontSize: 12, cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              推演
            </button>
          </div>
          {hypotheticalResult && (
            <pre style={{
              fontSize: 12, lineHeight: 1.6, color: 'var(--text-secondary)',
              whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)',
              background: 'var(--bg-secondary)', padding: 8, borderRadius: 4,
            }}>
              {hypotheticalResult}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
