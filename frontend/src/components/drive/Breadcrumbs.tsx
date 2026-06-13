import { ChevronRight, HardDrive } from 'lucide-react'
import { Link } from 'react-router-dom'

export interface BreadcrumbItem {
  id: string
  name: string
}

interface BreadcrumbsProps {
  ancestors: BreadcrumbItem[]
  current?: string
}

export function Breadcrumbs({ ancestors, current }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-sm">
      <Link
        to="/drive"
        className="flex shrink-0 items-center gap-1 text-muted-foreground transition-colors hover:text-foreground"
      >
        <HardDrive className="size-4" aria-hidden="true" />
        <span>My Drive</span>
      </Link>

      {ancestors.map((a) => (
        <span key={a.id} className="flex min-w-0 items-center gap-1">
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <Link
            to={`/drive/folder/${a.id}`}
            className="truncate text-muted-foreground transition-colors hover:text-foreground"
          >
            {a.name}
          </Link>
        </span>
      ))}

      {current && (
        <span className="flex min-w-0 items-center gap-1">
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="truncate font-medium" aria-current="page">
            {current}
          </span>
        </span>
      )}
    </nav>
  )
}
