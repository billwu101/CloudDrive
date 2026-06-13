import { Star } from 'lucide-react'

import type { DriveItemResponse } from '@/api/types'

import { FileIcon } from './FileIcon'

interface FileRowProps {
  item: DriveItemResponse
  selected: boolean
  onClick: (e: React.MouseEvent) => void
  onDoubleClick: () => void
  onContextMenu: (e: React.MouseEvent) => void
  onStarClick: (e: React.MouseEvent) => void
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function FileRow({ item, selected, onClick, onDoubleClick, onContextMenu, onStarClick }: FileRowProps) {
  return (
    <tr
      role="row"
      aria-selected={selected}
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onContextMenu={onContextMenu}
      className={`group cursor-pointer select-none border-b transition-colors last:border-b-0 hover:bg-accent/50 ${selected ? 'bg-accent' : ''}`}
    >
      <td className="py-2 pl-3 pr-2 w-8">
        <div className="flex size-5 items-center justify-center">
          <FileIcon mimeType={item.mime_type} isFolder={item.item_type === 'FOLDER'} />
        </div>
      </td>
      <td className="py-2 pr-3 text-sm font-medium truncate max-w-xs">{item.name}</td>
      <td className="py-2 pr-3 text-sm text-muted-foreground whitespace-nowrap">
        {item.item_type === 'FILE' && item.size_bytes != null ? formatBytes(item.size_bytes) : '—'}
      </td>
      <td className="py-2 pr-3 text-sm text-muted-foreground whitespace-nowrap">
        {formatDate(item.updated_at)}
      </td>
      <td className="py-2 pr-3 w-8">
        <button
          aria-label={item.is_starred ? 'Unstar' : 'Star'}
          onClick={onStarClick}
          className={`rounded p-0.5 transition-colors hover:text-amber-400 focus-visible:outline-none focus-visible:ring-2 ${item.is_starred ? 'text-amber-400' : 'text-transparent group-hover:text-muted-foreground'}`}
        >
          <Star className="size-4" fill={item.is_starred ? 'currentColor' : 'none'} aria-hidden="true" />
        </button>
      </td>
    </tr>
  )
}
