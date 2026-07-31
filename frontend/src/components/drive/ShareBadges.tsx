import { Link2, Users } from 'lucide-react'

interface ShareBadgesProps {
  /** Undefined on the guest side, where sharing state is the owner's business. */
  isSharedWithUsers?: boolean
  hasActivePublicLink?: boolean
}

/**
 * Marks an item in My Drive as not-private (proposal §29.2 rule 5).
 *
 * Two icons rather than one generic "shared" marker: a public link is the only
 * way in that needs no account at all, so it has to be distinguishable from
 * "shared with a specific person" at a glance.
 */
export function ShareBadges({ isSharedWithUsers, hasActivePublicLink }: ShareBadgesProps) {
  if (!isSharedWithUsers && !hasActivePublicLink) return null

  return (
    // shrink-0: in the grid the name sits beside these in a flex row, and a
    // long filename would otherwise squeeze the icons down to nothing.
    <span className="flex shrink-0 items-center gap-1 text-muted-foreground">
      {isSharedWithUsers && (
        <Users className="size-3.5" aria-label="Shared with other people" role="img" />
      )}
      {hasActivePublicLink && (
        <Link2 className="size-3.5" aria-label="Has an active public link" role="img" />
      )}
    </span>
  )
}
