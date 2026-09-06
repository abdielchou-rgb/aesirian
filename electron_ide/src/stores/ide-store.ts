// ─── Æsirian IDE 全局状态 ───
import { create } from 'zustand'

export type WritingMode = 'flow' | 'analysis'

export interface ToMCharacterState {
  name: string
  world_beliefs: Record<string, { value: string | boolean; confidence: number; source: string; is_erroneous: boolean }>
  about_others: Record<string, Record<string, { value: string | boolean; confidence: number }>>
  active_goals: { description: string; priority: number }[]
  secret_count: number
}

export interface TensionPoint {
  type: string
  description: string
  intensity: number
  involved: string[]
  suggestion: string
}

export interface GateResult {
  gate_id: string
  gate_name: string
  level: 'BLOCK' | 'WARN' | 'PASS'
  message: string
  detail?: string
  source?: string
  suggestion?: string
}

export interface AuditReport {
  chapter: number
  overall_score: number
  results: GateResult[]
  timestamp: string
}

export interface Relationship {
  source: string
  target: string
  type: string
  active: boolean
}

export interface ProjectStatus {
  project_id: string
  title: string
  current_chapter: number
  genre: string
}

interface IDEState {
  // 模式
  mode: WritingMode
  setMode: (m: WritingMode) => void

  // 项目
  project: ProjectStatus | null
  setProject: (p: ProjectStatus) => void

  // 画布文本
  canvasText: string
  setCanvasText: (t: string) => void
  appendCanvasText: (t: string) => void

  // 建议流
  suggestions: string[]
  setSuggestions: (s: string[]) => void
  clearSuggestions: () => void

  // 心智网格
  mindGrid: {
    characters: ToMCharacterState[]
    tension_points: TensionPoint[]
    relationships: Relationship[]
  }
  setMindGrid: (mg: any) => void

  // 审计报告
  auditReports: AuditReport[]
  addAuditReport: (r: AuditReport) => void

  // 侧边栏
  sidebarOpen: boolean
  toggleSidebar: () => void
  activePanel: 'mindgrid' | 'dashboard' | 'memory'
  setActivePanel: (p: 'mindgrid' | 'dashboard' | 'memory') => void

  // 连接状态
  backendConnected: boolean
  setBackendConnected: (c: boolean) => void
}

export const useStore = create<IDEState>((set) => ({
  mode: 'flow',
  setMode: (m) => set({ mode: m }),

  project: null,
  setProject: (p) => set({ project: p }),

  canvasText: '',
  setCanvasText: (t) => set({ canvasText: t }),
  appendCanvasText: (t) => set((s) => ({ canvasText: s.canvasText + t })),

  suggestions: [],
  setSuggestions: (s) => set({ suggestions: s }),
  clearSuggestions: () => set({ suggestions: [] }),

  mindGrid: { characters: [], tension_points: [], relationships: [] },
  setMindGrid: (mg) => set({ mindGrid: mg }),

  auditReports: [],
  addAuditReport: (r) => set((s) => ({ auditReports: [...s.auditReports, r] })),

  sidebarOpen: false,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  activePanel: 'mindgrid',
  setActivePanel: (p) => set({ activePanel: p }),

  backendConnected: false,
  setBackendConnected: (c) => set({ backendConnected: c }),
}))
