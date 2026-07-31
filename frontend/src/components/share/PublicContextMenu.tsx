import { Copy, Download, Edit2, Eye, FolderInput, Trash2 } from 'lucide-react'

import type { PublicItem } from '@/api/types'

/**
 * Right-click menu for a guest on an editor link (proposal §34.3).
 *
 * A separate component rather than flags on `FileContextMenu`: a guest has no
 * star, no re-sharing and no assistant skills, so three of that menu's entries
 * would have to be switched off. The two menus simply offer different sets of
 * actions, and encoding that as conditions inside one component makes every
 * future entry ask "which caller is this again?".
 */
interface PublicContextMenuProps {
  item: PublicItem
  position: { x: number; y: number }
  canEdit: boolean
  canDownload: boolean
  onClose: () => void
  onPreview: (item: PublicItem) => void
  onRename: (item: PublicItem) => void
  onMove: (item: PublicItem) => void
  onCopyName: (item: PublicItem) => void
  onTrash: (item: PublicItem) => void
  onDownload: (item: PublicItem) => void
}

const MenuItem = ({
  icon: Icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ElementType
  label: string
  onClick: React.MouseEventHandler<HTMLButtonElement>
  danger?: boolean
}) => (
  <button
    role="menuitem"
    onClick={onClick}
    className={`flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-left text-sm transition-colors hover:bg-accent ${danger ? 'text-destructive' : ''}`}
  >
    <Icon className="size-4" aria-hidden="true" />
    {label}
  </button>
)

export function PublicContextMenu({
  item,
  position,
  canEdit,
  canDownload,
  onClose,
  onPreview,
  onRename,
  onMove,
  onCopyName,
  onTrash,
  onDownload,
}: PublicContextMenuProps) {
  const wrap =
    (fn: () => void) =>
    (e: React.MouseEvent) => {
      e.stopPropagation()
      fn()
      onClose()
    }

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(event) => {
          event.preventDefault()
          onClose()
        }}
      />
      <div
        role="menu"
        className="fixed z-50 min-w-44 rounded-md border bg-popover p-1 shadow-md"
        style={{ top: position.y, left: position.x }}
      >
        {item.item_type === 'FILE' && (
          <MenuItem icon={Eye} label="Preview" onClick={wrap(() => onPreview(item))} />
        )}
        {item.item_type === 'FILE' && canDownload && (
          <MenuItem icon={Download} label="Download" onClick={wrap(() => onDownload(item))} />
        )}
        <MenuItem icon={Copy} label="Copy name" onClick={wrap(() => onCopyName(item))} />
        {canEdit && (
          <>
            <MenuItem icon={Edit2} label="Rename" onClick={wrap(() => onRename(item))} />
            <MenuItem icon={FolderInput} label="Move to" onClick={wrap(() => onMove(item))} />
            <MenuItem
              icon={Trash2}
              label="Move to trash"
              danger
              onClick={wrap(() => onTrash(item))}
            />
          </>
        )}
      </div>
    </>
  )
}
