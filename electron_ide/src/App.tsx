import React from 'react'
import { useStore } from './stores/ide-store'
import TopBar from './components/shared/TopBar'
import ModeToggle from './components/shared/ModeToggle'
import FlowCanvas from './components/flow_mode/FlowCanvas'
import AnalysisWorkspace from './components/analysis_mode/AnalysisWorkspace'
import SidePanel from './components/shared/SidePanel'

export default function App() {
  const mode = useStore((s) => s.mode)
  const sidebarOpen = useStore((s) => s.sidebarOpen)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopBar />
      <ModeToggle />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <main style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
          {mode === 'flow' ? <FlowCanvas /> : <AnalysisWorkspace />}
        </main>
        {sidebarOpen && <SidePanel />}
      </div>
    </div>
  )
}
