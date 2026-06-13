import {
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileVideo,
  Folder,
  Music,
  Package,
} from 'lucide-react'

interface FileIconProps {
  mimeType?: string | null
  isFolder?: boolean
  className?: string
}

export function FileIcon({ mimeType, isFolder, className = 'size-5' }: FileIconProps) {
  const colorClass = isFolder ? 'text-blue-500' : 'text-muted-foreground'
  const cls = `${className} ${colorClass}`

  if (isFolder) return <Folder className={cls} aria-hidden="true" />
  if (!mimeType) return <File className={cls} aria-hidden="true" />
  if (mimeType.startsWith('image/')) return <FileImage className={cls} aria-hidden="true" />
  if (mimeType.startsWith('video/')) return <FileVideo className={cls} aria-hidden="true" />
  if (mimeType.startsWith('audio/')) return <Music className={cls} aria-hidden="true" />
  if (mimeType === 'application/pdf') return <FileText className={cls} aria-hidden="true" />
  if (
    mimeType === 'application/msword' ||
    mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    mimeType === 'text/plain'
  )
    return <FileText className={cls} aria-hidden="true" />
  if (
    mimeType === 'application/vnd.ms-excel' ||
    mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
    mimeType === 'text/csv'
  )
    return <FileSpreadsheet className={cls} aria-hidden="true" />
  if (
    mimeType === 'application/zip' ||
    mimeType === 'application/x-tar' ||
    mimeType === 'application/gzip' ||
    mimeType === 'application/x-7z-compressed'
  )
    return <Package className={cls} aria-hidden="true" />

  return <File className={cls} aria-hidden="true" />
}
