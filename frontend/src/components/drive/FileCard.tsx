import { Star } from 'lucide-react'

import type { BrowsableItem } from '@/api/types'

import { FileIcon } from './FileIcon'
import { ShareBadges } from './ShareBadges'

interface FileCardProps {
  item: BrowsableItem
  selected: boolean
  onClick: (e: React.MouseEvent) => void
  onDoubleClick: () => void
  onContextMenu: (e: React.MouseEvent) => void
  /** Omitted for guests — starring needs an account to own the star. */
  onStarClick?: (e: React.MouseEvent) => void
  onCheckboxClick: (e: React.MouseEvent) => void
  dragging?: boolean
  dropTarget?: boolean
  onDragStart?: (e: React.DragEvent) => void
  onDragEnd?: () => void
  onDragOver?: (e: React.DragEvent) => void
  onDragLeave?: () => void
  onDrop?: (e: React.DragEvent) => void
}

export function FileCard({
  item,
  selected,
  onClick,
  onDoubleClick,
  onContextMenu,
  onStarClick,
  onCheckboxClick,
  dragging,
  dropTarget,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
}: FileCardProps) {
  const isFolder = item.item_type === 'FOLDER'

  return (
    <div
      role="option"
      aria-selected={selected}
      data-item-id={item.id}
      draggable
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onContextMenu={onContextMenu}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`group relative flex cursor-pointer select-none flex-col items-center gap-2 rounded-lg border p-3 transition-colors hover:bg-accent/50 ${selected ? 'border-primary bg-accent' : 'border-border'} ${dragging ? 'opacity-40' : ''} ${dropTarget ? 'border-primary ring-2 ring-primary' : ''}`}
    >
      {/* Checkbox top-left: visible on hover or when selected */}
      <input
        type="checkbox"
        checked={selected}
        onChange={() => {}}
        onClick={(e) => { e.stopPropagation(); onCheckboxClick(e) }}
        aria-label={`Select ${item.name}`}
        className={`absolute left-2 top-2 size-4 cursor-pointer accent-primary transition-opacity ${selected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
      />

      {/* Star top-right */}
      {onStarClick && (
        <button
          aria-label={item.is_starred ? 'Unstar' : 'Star'}
          onClick={onStarClick}
          className={`absolute right-2 top-2 rounded p-0.5 transition-colors hover:text-amber-400 focus-visible:outline-none focus-visible:ring-2 ${item.is_starred ? 'text-amber-400' : 'text-transparent group-hover:text-muted-foreground'}`}
        >
          <Star className="size-4" fill={item.is_starred ? 'currentColor' : 'none'} aria-hidden="true" />
        </button>
      )}

      <div className={`flex size-12 items-center justify-center rounded-lg ${isFolder ? 'bg-blue-50' : 'bg-muted'}`}>
        <FileIcon
          mimeType={item.mime_type}
          isFolder={isFolder}
          className={`size-7 ${isFolder ? 'text-blue-500' : 'text-muted-foreground'}`}
        />
      </div>

      <div className="flex w-full min-w-0 items-center justify-center gap-1">
        <p className="truncate text-center text-xs font-medium" title={item.name}>
          {item.name}
        </p>
        <ShareBadges
          isSharedWithUsers={item.is_shared_with_users}
          hasActivePublicLink={item.has_active_public_link}
        />
      </div>
    </div>
  )
}
