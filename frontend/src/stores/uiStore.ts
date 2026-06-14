import { create } from 'zustand'

export type ViewMode = 'grid' | 'list'

interface ContextMenu {
  itemId: string | null
  x: number
  y: number
}

interface UIState {
  sidebarCollapsed: boolean
  viewMode: ViewMode
  selectedItemIds: Set<string>
  previewItemId: string | null
  shareItemId: string | null
  contextMenu: ContextMenu

  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  setViewMode: (mode: ViewMode) => void
  selectItem: (id: string, multi?: boolean) => void
  selectAll: (ids: string[]) => void
  clearSelection: () => void
  setPreviewItem: (id: string | null) => void
  setShareItem: (id: string | null) => void
  openContextMenu: (itemId: string, x: number, y: number) => void
  closeContextMenu: () => void
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarCollapsed: false,
  viewMode: 'grid',
  selectedItemIds: new Set<string>(),
  previewItemId: null,
  shareItemId: null,
  contextMenu: { itemId: null, x: 0, y: 0 },

  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  setViewMode: (mode) => set({ viewMode: mode }),

  selectItem: (id, multi = false) =>
    set((s) => {
      if (multi) {
        const next = new Set(s.selectedItemIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return { selectedItemIds: next }
      }
      return { selectedItemIds: new Set([id]) }
    }),

  selectAll: (ids) => set({ selectedItemIds: new Set(ids) }),

  clearSelection: () => set({ selectedItemIds: new Set<string>() }),

  setPreviewItem: (id) => set({ previewItemId: id }),

  setShareItem: (id) => set({ shareItemId: id }),

  openContextMenu: (itemId, x, y) =>
    set({ contextMenu: { itemId, x, y } }),

  closeContextMenu: () =>
    set({ contextMenu: { itemId: null, x: 0, y: 0 } }),
}))
