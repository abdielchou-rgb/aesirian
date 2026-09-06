import React, { useEffect, useRef, useCallback } from 'react'
import { useStore } from '../../stores/ide-store'

export default function MindGrid() {
  const mindGrid = useStore((s) => s.mindGrid)
  const svgRef = useRef<SVGSVGElement>(null)
  const animationRef = useRef<number>(0)

  // D3-force 模拟
  useEffect(() => {
    if (!svgRef.current || !mindGrid.characters.length) return

    const svg = svgRef.current
    const width = svg.clientWidth || 400
    const height = svg.clientHeight || 400

    // 清空
    while (svg.firstChild) svg.removeChild(svg.firstChild)

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs')
    const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter')
    filter.setAttribute('id', 'shadow')
    filter.innerHTML = '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.1"/>'
    defs.appendChild(filter)
    svg.appendChild(defs)

    const names = mindGrid.characters.map(c => c.name)
    const nodePositions: Record<string, { x: number; y: number }> = {}
    const centerX = width / 2
    const centerY = height / 2
    const radius = Math.min(width, height) * 0.3

    // 圆形布局
    names.forEach((name, i) => {
      const angle = (i / names.length) * Math.PI * 2 - Math.PI / 2
      nodePositions[name] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      }
    })

    // 边
    mindGrid.relationships.forEach((rel) => {
      const src = nodePositions[rel.source]
      const tgt = nodePositions[rel.target]
      if (!src || !tgt) return

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
      line.setAttribute('x1', String(src.x))
      line.setAttribute('y1', String(src.y))
      line.setAttribute('x2', String(tgt.x))
      line.setAttribute('y2', String(tgt.y))
      line.setAttribute('stroke', rel.active ? 'var(--border)' : '#ddd')
      line.setAttribute('stroke-width', rel.active ? '1.5' : '0.8')
      line.setAttribute('stroke-dasharray', rel.active ? '' : '4,3')
      svg.appendChild(line)

      // 关系标签
      const midX = (src.x + tgt.x) / 2
      const midY = (src.y + tgt.y) / 2
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      label.setAttribute('x', String(midX))
      label.setAttribute('y', String(midY - 4))
      label.setAttribute('text-anchor', 'middle')
      label.setAttribute('font-size', '9')
      label.setAttribute('fill', 'var(--text-muted)')
      label.textContent = rel.type
      svg.appendChild(label)
    })

    // 角色节点
    mindGrid.characters.forEach((char) => {
      const pos = nodePositions[char.name]
      if (!pos) return

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      g.setAttribute('transform', `translate(${pos.x}, ${pos.y})`)
      g.style.cursor = 'pointer'

      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      circle.setAttribute('r', '22')
      circle.setAttribute('fill', char.secret_count > 0 ? '#f0d5c0' : '#e8e4de')
      circle.setAttribute('stroke', 'var(--accent)')
      circle.setAttribute('stroke-width', '1.5')
      circle.setAttribute('filter', 'url(#shadow)')
      g.appendChild(circle)

      // 首字母
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('dy', '4')
      text.setAttribute('font-size', '13')
      text.setAttribute('font-weight', '600')
      text.setAttribute('fill', 'var(--text-primary)')
      text.textContent = char.name[0]
      g.appendChild(text)

      // 标签
      const nameLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      nameLabel.setAttribute('text-anchor', 'middle')
      nameLabel.setAttribute('y', '34')
      nameLabel.setAttribute('font-size', '10')
      nameLabel.setAttribute('fill', 'var(--text-secondary)')
      nameLabel.textContent = char.name
      g.appendChild(nameLabel)

      // 秘密指示
      if (char.secret_count > 0) {
        const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
        dot.setAttribute('cx', '16')
        dot.setAttribute('cy', '-16')
        dot.setAttribute('r', '4')
        dot.setAttribute('fill', 'var(--danger)')
        g.appendChild(dot)
      }

      svg.appendChild(g)

      // 悬停提示 —— 信念气泡
      const tooltip = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      tooltip.setAttribute('x', String(pos.x + 30))
      tooltip.setAttribute('y', String(pos.y - 20))
      tooltip.setAttribute('font-size', '9')
      tooltip.setAttribute('fill', 'var(--text-muted)')
      tooltip.setAttribute('opacity', '0')
      const beliefs = Object.entries(char.world_beliefs).slice(0, 2)
        .map(([k, v]) => `${k}:${v.value}`).join(', ')
      tooltip.textContent = beliefs || '...'
      svg.appendChild(tooltip)

      g.addEventListener('mouseenter', () => tooltip.setAttribute('opacity', '1'))
      g.addEventListener('mouseleave', () => tooltip.setAttribute('opacity', '0'))
    })
  }, [mindGrid])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '8px 12px', borderBottom: '1px solid var(--border)' }}>
        角色心智网格
        {mindGrid.tension_points.length > 0 && (
          <span style={{ marginLeft: 8, color: 'var(--danger)', fontSize: 10 }}>
            · {mindGrid.tension_points.length} 个张力点
          </span>
        )}
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        <svg ref={svgRef} width="100%" height="100%" />
      </div>
    </div>
  )
}
