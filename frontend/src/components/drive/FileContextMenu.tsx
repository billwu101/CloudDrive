import {
  Download,
  Edit2,
  Eye,
  FolderInput,
  Link2,
  Share2,
  Sparkles,
  Star,
  StarOff,
  Trash2,
} from 'lucide-react'

import type { DriveItemResponse } from '@/api/types'

export interface AssistantContextMenuAction {
  skillId: string
  label: string
  handler: string
}

interface FileContextMenuProps {
  item: DriveItemResponse
  position: { x: number; y: number }
  assistantActions?: AssistantContextMenuAction[]
  onClose: () => void
  onPreview: (item: DriveItemResponse) => void
  onRename: (item: DriveItemResponse) => void
  onMove: (item: DriveItemResponse) => void
  onShare: (item: DriveItemResponse) => void
  onCopyLink: (item: DriveItemResponse) => void
  onToggleStar: (item: DriveItemResponse) => void
  onTrash: (item: DriveItemResponse) => void
  onDownload?: (item: DriveItemResponse) => void
  onAssistantAction?: (action: AssistantContextMenuAction, item: DriveItemResponse) => void
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

export function FileContextMenu({
  item,
  position,
  assistantActions = [],
  onClose,
  onPreview,
  onRename,
  onMove,
  onShare,
  onCopyLink,
  onToggleStar,
  onTrash,
  onDownload,
  onAssistantAction,
}: FileContextMenuProps) {
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
        <MenuItem icon={Edit2} label="Rename" onClick={wrap(() => onRename(item))} />
        <MenuItem icon={FolderInput} label="Move to" onClick={wrap(() => onMove(item))} />
        <MenuItem icon={Share2} label="Share" onClick={wrap(() => onShare(item))} />
        <MenuItem icon={Link2} label="Copy link" onClick={wrap(() => onCopyLink(item))} />
        <MenuItem
          icon={item.is_starred ? StarOff : Star}
          label={item.is_starred ? 'Unstar' : 'Star'}
          onClick={wrap(() => onToggleStar(item))}
        />
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
        <div className="my-1 h-px bg-border" />
        <MenuItem icon={Trash2} label="Move to trash" onClick={wrap(() => onTrash(item))} danger />
      </div>
    </>
  )
}
