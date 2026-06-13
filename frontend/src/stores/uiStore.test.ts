import { beforeEach, describe, expect, it } from 'vitest'

import { useUIStore } from './uiStore'

beforeEach(() => {
  useUIStore.setState({
    sidebarCollapsed: false,
    viewMode: 'grid',
    selectedItemIds: new Set(),
    previewItemId: null,
    shareItemId: null,
    contextMenu: { itemId: null, x: 0, y: 0 },
  })
})

describe('sidebar', () => {
  it('toggles collapsed state', () => {
    const { toggleSidebar } = useUIStore.getState()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
    toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('sets collapsed explicitly', () => {
    useUIStore.getState().setSidebarCollapsed(true)
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
  })
})

describe('viewMode', () => {
  it('switches to list', () => {
    useUIStore.getState().setViewMode('list')
    expect(useUIStore.getState().viewMode).toBe('list')
  })

  it('switches back to grid', () => {
    useUIStore.setState({ viewMode: 'list' })
    useUIStore.getState().setViewMode('grid')
    expect(useUIStore.getState().viewMode).toBe('grid')
  })
})

describe('selectedItemIds', () => {
  it('selects a single item', () => {
    useUIStore.getState().selectItem('a')
    expect(useUIStore.getState().selectedItemIds.has('a')).toBe(true)
    expect(useUIStore.getState().selectedItemIds.size).toBe(1)
  })

  it('single-select replaces previous selection', () => {
    useUIStore.getState().selectItem('a')
    useUIStore.getState().selectItem('b')
    expect(useUIStore.getState().selectedItemIds.has('a')).toBe(false)
    expect(useUIStore.getState().selectedItemIds.has('b')).toBe(true)
  })

  it('multi-select adds to selection', () => {
    useUIStore.getState().selectItem('a')
    useUIStore.getState().selectItem('b', true)
    expect(useUIStore.getState().selectedItemIds.size).toBe(2)
  })

  it('multi-select deselects already-selected item', () => {
    useUIStore.getState().selectItem('a')
    useUIStore.getState().selectItem('a', true)
    expect(useUIStore.getState().selectedItemIds.has('a')).toBe(false)
  })

  it('clears selection', () => {
    useUIStore.getState().selectItem('a')
    useUIStore.getState().clearSelection()
    expect(useUIStore.getState().selectedItemIds.size).toBe(0)
  })
})

describe('previewItemId', () => {
  it('sets and clears preview item', () => {
    useUIStore.getState().setPreviewItem('item-1')
    expect(useUIStore.getState().previewItemId).toBe('item-1')
    useUIStore.getState().setPreviewItem(null)
    expect(useUIStore.getState().previewItemId).toBeNull()
  })
})

describe('shareItemId', () => {
  it('sets and clears share item', () => {
    useUIStore.getState().setShareItem('item-2')
    expect(useUIStore.getState().shareItemId).toBe('item-2')
    useUIStore.getState().setShareItem(null)
    expect(useUIStore.getState().shareItemId).toBeNull()
  })
})

describe('contextMenu', () => {
  it('opens with position and itemId', () => {
    useUIStore.getState().openContextMenu('item-3', 100, 200)
    const menu = useUIStore.getState().contextMenu
    expect(menu.itemId).toBe('item-3')
    expect(menu.x).toBe(100)
    expect(menu.y).toBe(200)
  })

  it('closes and resets state', () => {
    useUIStore.getState().openContextMenu('item-3', 100, 200)
    useUIStore.getState().closeContextMenu()
    const menu = useUIStore.getState().contextMenu
    expect(menu.itemId).toBeNull()
    expect(menu.x).toBe(0)
    expect(menu.y).toBe(0)
  })
})
