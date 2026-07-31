import type { BrowsableItem } from '@/api/types'
import type { DragMove } from '@/hooks/useDragMove'

import { FileCard } from './FileCard'

/**
 * Generic over the item so each caller gets its own type back in the handlers
 * (design §5.9.6 point 10): My Drive keeps its full `DriveItemResponse`, the
 * guest page its narrower `PublicItem`. A plain `BrowsableItem` parameter
 * would be unsound — the callback would receive less than the caller declared.
 */
interface FileGridProps<T extends BrowsableItem> {
  items: T[]
  selectedIds: Set<string>
  onItemClick: (item: T, e: React.MouseEvent) => void
  onItemDoubleClick: (item: T) => void
  onItemContextMenu: (item: T, e: React.MouseEvent) => void
  /** Omitted for guests — starring needs an account to own the star. */
  onStarClick?: (item: T, e: React.MouseEvent) => void
  onCheckboxClick: (item: T, e: React.MouseEvent) => void
  drag?: DragMove
}

export function FileGrid<T extends BrowsableItem>({
  items,
  selectedIds,
  onItemClick,
  onItemDoubleClick,
  onItemContextMenu,
  onStarClick,
  onCheckboxClick,
  drag,
}: FileGridProps<T>) {
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
          onStarClick={onStarClick && ((e) => onStarClick(item, e))}
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
