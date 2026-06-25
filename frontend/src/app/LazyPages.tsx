import { lazy, Suspense } from 'react'

const DrivePage = lazy(async () => {
  const { DrivePage } = await import('@/pages/DrivePage')
  return { default: DrivePage }
})
const RecentPage = lazy(async () => {
  const { RecentPage } = await import('@/pages/RecentPage')
  return { default: RecentPage }
})
const StarredPage = lazy(async () => {
  const { StarredPage } = await import('@/pages/StarredPage')
  return { default: StarredPage }
})
const SharedPage = lazy(async () => {
  const { SharedPage } = await import('@/pages/SharedPage')
  return { default: SharedPage }
})
const TrashPage = lazy(async () => {
  const { TrashPage } = await import('@/pages/TrashPage')
  return { default: TrashPage }
})
const SearchPage = lazy(async () => {
  const { SearchPage } = await import('@/pages/SearchPage')
  return { default: SearchPage }
})
const SettingsPage = lazy(async () => {
  const { SettingsPage } = await import('@/pages/SettingsPage')
  return { default: SettingsPage }
})
const SkillsPage = lazy(async () => {
  const { SkillsPage } = await import('@/pages/SkillsPage')
  return { default: SkillsPage }
})
const TimeMachinePage = lazy(async () => {
  const { TimeMachinePage } = await import('@/pages/TimeMachinePage')
  return { default: TimeMachinePage }
})

function PageFallback() {
  return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
}

export function LazyDrivePage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <DrivePage />
    </Suspense>
  )
}

export function LazyRecentPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <RecentPage />
    </Suspense>
  )
}

export function LazyStarredPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <StarredPage />
    </Suspense>
  )
}

export function LazySharedPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <SharedPage />
    </Suspense>
  )
}

export function LazyTrashPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <TrashPage />
    </Suspense>
  )
}

export function LazySearchPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <SearchPage />
    </Suspense>
  )
}

export function LazySettingsPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <SettingsPage />
    </Suspense>
  )
}

export function LazySkillsPage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <SkillsPage />
    </Suspense>
  )
}

export function LazyTimeMachinePage() {
  return (
    <Suspense fallback={<PageFallback />}>
      <TimeMachinePage />
    </Suspense>
  )
}
