import { Link, Users } from 'lucide-react'
import { useState } from 'react'

import { ShareLinkPanel } from './ShareLinkPanel'
import { UserShareForm } from './UserShareForm'

interface ShareDialogProps {
  open: boolean
  itemId: string
  itemName: string
  onClose: () => void
}

type Tab = 'people' | 'link'

export function ShareDialog({ open, itemId, itemName, onClose }: ShareDialogProps) {
  const [tab, setTab] = useState<Tab>('people')

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-dialog-title"
        className="w-full max-w-md rounded-lg border bg-popover shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b px-5 py-4">
          <h2 id="share-dialog-title" className="text-sm font-semibold">
            Share "{itemName}"
          </h2>
        </div>

        {/* Tabs */}
        <div className="flex border-b">
          {([
            { key: 'people', label: 'People', icon: Users },
            { key: 'link', label: 'Link', icon: Link },
          ] as const).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex flex-1 items-center justify-center gap-1.5 px-4 py-2.5 text-sm transition-colors ${tab === key ? 'border-b-2 border-primary font-medium text-primary' : 'text-muted-foreground hover:text-foreground'}`}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-5">
          {tab === 'people' ? (
            <UserShareForm itemId={itemId} />
          ) : (
            <ShareLinkPanel itemId={itemId} />
          )}
        </div>

        <div className="flex justify-end border-t px-5 py-4">
          <button
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
