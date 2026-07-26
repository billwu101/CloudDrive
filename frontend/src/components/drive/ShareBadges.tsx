import { Link2, Users } from 'lucide-react'

interface ShareBadgesProps {
  isSharedWithUsers: boolean
  hasActivePublicLink: boolean
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
    <span className="flex items-center gap-1 text-muted-foreground">
      {isSharedWithUsers && (
        <Users className="size-3.5" aria-label="Shared with other people" role="img" />
      )}
      {hasActivePublicLink && (
        <Link2 className="size-3.5" aria-label="Has an active public link" role="img" />
      )}
    </span>
  )
}
