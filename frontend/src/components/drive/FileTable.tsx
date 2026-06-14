import { useEffect, useRef } from 'react'

import type { DriveItemResponse } from '@/api/types'

import { FileRow } from './FileRow'

interface FileTableProps {
  items: DriveItemResponse[]
  selectedIds: Set<string>
  onItemClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  onItemDoubleClick: (item: DriveItemResponse) => void
  onItemContextMenu: (item: DriveItemResponse, e: React.MouseEvent) => void
  onStarClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  onCheckboxClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  onSelectAll: () => void
}

export function FileTable({
  items,
  selectedIds,
  onItemClick,
  onItemDoubleClick,
  onItemContextMenu,
  onStarClick,
  onCheckboxClick,
  onSelectAll,
}: FileTableProps) {
  const allSelected = items.length > 0 && items.every((i) => selectedIds.has(i.id))
  const someSelected = !allSelected && items.some((i) => selectedIds.has(i.id))

  const headerCheckboxRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (headerCheckboxRef.current) {
      headerCheckboxRef.current.indeterminate = someSelected
    }
  }, [someSelected])

  return (
    <table className="w-full table-fixed border-collapse text-left">
      <colgroup>
        <col className="w-8" />
        <col />
        <col className="w-24" />
        <col className="w-32" />
        <col className="w-8" />
      </colgroup>
      <thead>
        <tr className="border-b text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <th className="py-2 pl-3">
            <input
              ref={headerCheckboxRef}
              type="checkbox"
              checked={allSelected}
              onChange={(e) => { e.stopPropagation(); onSelectAll() }}
              aria-label="Select all"
              className="size-4 cursor-pointer accent-primary"
            />
          </th>
          <th className="py-2 pr-3">Name</th>
          <th className="py-2 pr-3">Size</th>
          <th className="py-2 pr-3">Modified</th>
          <th className="py-2 pr-3" />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <FileRow
            key={item.id}
            item={item}
            selected={selectedIds.has(item.id)}
            onClick={(e) => onItemClick(item, e)}
            onDoubleClick={() => onItemDoubleClick(item)}
            onContextMenu={(e) => onItemContextMenu(item, e)}
            onStarClick={(e) => onStarClick(item, e)}
            onCheckboxClick={(e) => onCheckboxClick(item, e)}
          />
        ))}
      </tbody>
    </table>
  )
}
