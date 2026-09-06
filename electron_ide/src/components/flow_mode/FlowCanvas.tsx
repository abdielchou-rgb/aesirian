import React, { useState, useCallback, useRef, useEffect } from 'react'
import { useStore } from '../../stores/ide-store'

export default function FlowCanvas() {
  const canvasText = useStore((s) => s.canvasText)
  const suggestions = useStore((s) => s.suggestions)
  const appendCanvasText = useStore((s) => s.appendCanvasText)
  const clearSuggestions = useStore((s) => s.clearSuggestions)

  const [localText, setLocalText] = useState(canvasText)
  const textRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Ctrl+Enter: 触发续写建议
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault()
      // TODO: 调用后端续写引擎
      // 占位模拟
      const suggestions = [
        '他推开门的时候，雨刚好停了。',
        '"你不该来这里的。"她的声音比预想中平静。',
        '桌上的信已经拆开了——三天前的邮戳。',
      ]
      useStore.getState().setSuggestions(suggestions)
    }
  }, [])

  // 同步localText到store
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localText !== canvasText) {
        useStore.getState().setCanvasText(localText)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [localText, canvasText])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
      {/* 提示条 */}
      {!localText && (
        <div style={{
          position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
          textAlign: 'center', color: 'var(--text-muted)', pointerEvents: 'none',
          fontSize: 15, lineHeight: 1.8,
        }}>
          开始写你的故事……<br />
          <span style={{ fontSize: 12 }}>写完一段后按 Ctrl+Enter 获取续写方向</span>
        </div>
      )}

      {/* 主画布 */}
      <textarea
        ref={textRef}
        value={localText}
        onChange={(e) => setLocalText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder=""
        style={{
          flex: 1, border: 'none', resize: 'none', outline: 'none', padding: '40px 48px',
          fontFamily: 'var(--font-body)', fontSize: 16, lineHeight: 1.9,
          color: 'var(--text-primary)', background: 'transparent',
        }}
      />

      {/* 建议流 */}
      {suggestions.length > 0 && (
        <div style={{
          borderTop: '1px solid var(--border)', padding: '12px 48px',
          background: 'var(--bg-card)', flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
            续写方向 — 点击选择，按 Esc 关闭
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => {
                  appendCanvasText('\n\n' + s)
                  clearSuggestions()
                }}
                style={{
                  textAlign: 'left', padding: '8px 12px', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', cursor: 'pointer',
                  background: 'var(--bg-primary)', fontSize: 14, color: 'var(--text-primary)',
                  transition: 'all 0.12s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-secondary)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'var(--bg-primary)'}
              >
                <span style={{ color: 'var(--accent)', fontWeight: 600, marginRight: 8 }}>
                  {String.fromCharCode(65 + i)}
                </span>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
