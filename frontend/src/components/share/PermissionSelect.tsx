import type { Permission } from '@/hooks/useShare'

const OPTIONS: { value: Permission; label: string }[] = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'downloader', label: 'Downloader' },
  { value: 'editor', label: 'Editor' },
]

interface PermissionSelectProps {
  value: Permission
  onChange: (value: Permission) => void
  disabled?: boolean
}

export function PermissionSelect({ value, onChange, disabled }: PermissionSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as Permission)}
      disabled={disabled}
      className="rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:opacity-50"
      aria-label="Permission level"
    >
      {OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}
