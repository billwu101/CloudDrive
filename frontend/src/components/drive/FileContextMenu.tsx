import {
  Copy,
  Download,
  Edit2,
  Eye,
  FolderInput,
  Share2,
  Sparkles,
  Star,
  StarOff,
  Trash2,
} from 'lucide-react'

import type { BrowsableItem } from '@/api/types'

export interface AssistantContextMenuAction {
  skillId: string
  label: string
  handler: string
}

/**
 * Handlers are optional and an absent handler renders no entry (design §5.9.6
 * point 10): the guest page shares this menu, and what a guest cannot do is
 * expressed by not wiring the capability — never by an "is guest" flag.
 */
interface FileContextMenuProps<T extends BrowsableItem> {
  item: T
  position: { x: number; y: number }
  assistantActions?: AssistantContextMenuAction[]
  onClose: () => void
  onPreview: (item: T) => void
  onRename?: (item: T) => void
  onMove?: (item: T) => void
  onShare?: (item: T) => void
  onCopyName: (item: T) => void
  onToggleStar?: (item: T) => void
  onTrash?: (item: T) => void
  onDownload?: (item: T) => void
  onAssistantAction?: (action: AssistantContextMenuAction, item: T) => void
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

export function FileContextMenu<T extends BrowsableItem>({
  item,
  position,
  assistantActions = [],
  onClose,
  onPreview,
  onRename,
  onMove,
  onShare,
  onCopyName,
  onToggleStar,
  onTrash,
  onDownload,
  onAssistantAction,
}: FileContextMenuProps<T>) {
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
        {onRename && (
          <MenuItem icon={Edit2} label="Rename" onClick={wrap(() => onRename(item))} />
        )}
        {onMove && (
          <MenuItem icon={FolderInput} label="Move to" onClick={wrap(() => onMove(item))} />
        )}
        {onShare && (
          <MenuItem icon={Share2} label="Share" onClick={wrap(() => onShare(item))} />
        )}
        <MenuItem icon={Copy} label="Copy name" onClick={wrap(() => onCopyName(item))} />
        {onToggleStar && (
          <MenuItem
            icon={item.is_starred ? StarOff : Star}
            label={item.is_starred ? 'Unstar' : 'Star'}
            onClick={wrap(() => onToggleStar(item))}
          />
        )}
        {item.item_type === 'FILE' && onDownload && (
          <MenuItem icon={Download} label="Download" onClick={wrap(() => onDownload(item))} />
        )}
        {assistantActions.length > 0 && (
          <>
            <div className="my-1 h-px bg-border" />
            {assistantActions.map((action) => (
              <MenuItem
                key={`${action.skillId}:${action.handler}`}
                icon={Sparkles}
                label={action.label}
                onClick={wrap(() => onAssistantAction?.(action, item))}
              />
            ))}
          </>
        )}
        {onTrash && (
          <>
            <div className="my-1 h-px bg-border" />
            <MenuItem
              icon={Trash2}
              label="Move to trash"
              onClick={wrap(() => onTrash(item))}
              danger
            />
          </>
        )}
      </div>
    </>
  )
}
