import { Search } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

export function SearchPage() {
  const [params] = useSearchParams()
  const query = params.get('q') ?? ''

  return (
    <div className="flex h-full flex-col gap-4">
      <h1 className="text-lg font-semibold">
        {query ? `Search results for "${query}"` : 'Search'}
      </h1>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
        <Search className="size-12" aria-hidden="true" />
        <p className="text-sm">{query ? 'No results found' : 'Enter a search term above'}</p>
      </div>
    </div>
  )
}
