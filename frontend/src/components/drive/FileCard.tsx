import { Star } from 'lucide-react'

import type { DriveItemResponse } from '@/api/types'

import { FileIcon } from './FileIcon'

interface FileCardProps {
  item: DriveItemResponse
  selected: boolean
  onClick: (e: React.MouseEvent) => void
  onDoubleClick: () => void
  onContextMenu: (e: React.MouseEvent) => void
  onStarClick: (e: React.MouseEvent) => void
}

export function FileCard({ item, selected, onClick, onDoubleClick, onContextMenu, onStarClick }: FileCardProps) {
  const isFolder = item.item_type === 'FOLDER'

  return (
    <div
      role="option"
      aria-selected={selected}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onContextMenu={onContextMenu}
      className={`group relative flex cursor-pointer select-none flex-col items-center gap-2 rounded-lg border p-3 transition-colors hover:bg-accent/50 ${selected ? 'border-primary bg-accent' : 'border-border'}`}
    >
      <button
        aria-label={item.is_starred ? 'Unstar' : 'Star'}
        onClick={onStarClick}
        className={`absolute right-2 top-2 rounded p-0.5 transition-colors hover:text-amber-400 focus-visible:outline-none focus-visible:ring-2 ${item.is_starred ? 'text-amber-400' : 'text-transparent group-hover:text-muted-foreground'}`}
      >
        <Star className="size-4" fill={item.is_starred ? 'currentColor' : 'none'} aria-hidden="true" />
      </button>

      <div className={`flex size-12 items-center justify-center rounded-lg ${isFolder ? 'bg-blue-50' : 'bg-muted'}`}>
        <FileIcon
          mimeType={item.mime_type}
          isFolder={isFolder}
          className={`size-7 ${isFolder ? 'text-blue-500' : 'text-muted-foreground'}`}
        />
      </div>

      <p className="w-full truncate text-center text-xs font-medium" title={item.name}>
        {item.name}
      </p>
    </div>
  )
}
