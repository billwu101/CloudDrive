import { LayoutGrid, List, Search } from 'lucide-react'

import { cn } from '@/lib/utils'
import { useUIStore } from '@/stores/uiStore'

interface TopBarProps {
  title?: string
  onSearch?: (query: string) => void
}

export function TopBar({ title, onSearch }: TopBarProps) {
  const { viewMode, setViewMode } = useUIStore()

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
      {title && (
        <h1 className="text-base font-semibold text-foreground">{title}</h1>
      )}

      {/* Search bar */}
      <div className="relative flex-1 max-w-md">
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <input
          type="search"
          placeholder="Search in Drive"
          className="w-full rounded-md border border-input bg-muted py-1.5 pl-8 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30"
          onChange={(e) => onSearch?.(e.target.value)}
          aria-label="Search drive"
        />
      </div>

      {/* View mode toggle */}
      <div
        className="flex items-center gap-0.5 rounded-md border border-border p-0.5"
        role="group"
        aria-label="View mode"
      >
        <button
          type="button"
          className={cn(
            'flex size-7 items-center justify-center rounded text-sm transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            viewMode === 'grid'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
          onClick={() => setViewMode('grid')}
          aria-pressed={viewMode === 'grid'}
          aria-label="Grid view"
          title="Grid view"
        >
          <LayoutGrid className="size-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          className={cn(
            'flex size-7 items-center justify-center rounded text-sm transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            viewMode === 'list'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground',
          )}
          onClick={() => setViewMode('list')}
          aria-pressed={viewMode === 'list'}
          aria-label="List view"
          title="List view"
        >
          <List className="size-4" aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}
