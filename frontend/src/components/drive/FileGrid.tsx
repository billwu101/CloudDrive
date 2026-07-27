import type { DriveItemResponse } from '@/api/types'
import type { DragMove } from '@/hooks/useDragMove'

import { FileCard } from './FileCard'

interface FileGridProps {
  items: DriveItemResponse[]
  selectedIds: Set<string>
  onItemClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  onItemDoubleClick: (item: DriveItemResponse) => void
  onItemContextMenu: (item: DriveItemResponse, e: React.MouseEvent) => void
  onStarClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  onCheckboxClick: (item: DriveItemResponse, e: React.MouseEvent) => void
  drag?: DragMove
}

export function FileGrid({
  items,
  selectedIds,
  onItemClick,
  onItemDoubleClick,
  onItemContextMenu,
  onStarClick,
  onCheckboxClick,
  drag,
}: FileGridProps) {
  return (
    <div
      role="listbox"
      aria-multiselectable="true"
      aria-label="Files and folders"
      className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-3"
    >
      {items.map((item) => (
        <FileCard
          key={item.id}
          item={item}
          selected={selectedIds.has(item.id)}
          onClick={(e) => onItemClick(item, e)}
          onDoubleClick={() => onItemDoubleClick(item)}
          onContextMenu={(e) => onItemContextMenu(item, e)}
          onStarClick={(e) => onStarClick(item, e)}
          onCheckboxClick={(e) => onCheckboxClick(item, e)}
          dragging={drag?.draggingIds.has(item.id)}
          dropTarget={drag?.dropTargetId === item.id}
          onDragStart={drag ? (e) => drag.onItemDragStart(item, e) : undefined}
          onDragEnd={drag?.onItemDragEnd}
          onDragOver={drag ? (e) => drag.onItemDragOver(item, e) : undefined}
          onDragLeave={drag ? () => drag.onItemDragLeave(item) : undefined}
          onDrop={drag ? (e) => drag.onItemDrop(item, e) : undefined}
        />
      ))}
    </div>
  )
}
