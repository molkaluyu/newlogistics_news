import { useSearchParams } from 'react-router-dom'
import { Search, X } from 'lucide-react'
import { cn, transportIcons } from '@/lib/utils'

interface ArticleFiltersProps {
  total?: number
}

export function ArticleFilters({ total }: ArticleFiltersProps) {
  const [searchParams, setSearchParams] = useSearchParams()

  // Read current filters from URL
  const currentFilters = {
    search: searchParams.get('search') || '',
    transport_mode: searchParams.get('transport_mode') || '',
    topic: searchParams.get('topic') || '',
    sentiment: searchParams.get('sentiment') || '',
    urgency: searchParams.get('urgency') || '',
    language: searchParams.get('language') || '',
    source_id: searchParams.get('source_id') || '',
    from_date: searchParams.get('from_date') || '',
    to_date: searchParams.get('to_date') || '',
  }

  const setFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    params.delete('page') // reset page on filter change
    setSearchParams(params)
  }

  const clearAll = () => setSearchParams({})

  // Count active filters
  const activeCount = Object.values(currentFilters).filter((v) => v !== '').length

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search articles..."
          value={currentFilters.search}
          onChange={(e) => setFilter('search', e.target.value)}
          className="w-full rounded-md border border-border bg-background py-2 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none"
        />
        {currentFilters.search && (
          <button
            onClick={() => setFilter('search', '')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {/* Transport Mode toggle buttons */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Transport Mode
        </label>
        <div className="flex flex-wrap gap-1.5">
          {['', 'ocean', 'air', 'road', 'rail'].map((mode) => (
            <button
              key={mode}
              onClick={() => setFilter('transport_mode', mode)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                currentFilters.transport_mode === mode
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-accent',
              )}
            >
              {mode === '' ? 'All' : `${transportIcons[mode] || ''} ${mode}`}
            </button>
          ))}
        </div>
      </div>

      {/* Sentiment toggle */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Sentiment
        </label>
        <div className="flex flex-wrap gap-1.5">
          {['', 'positive', 'neutral', 'negative'].map((s) => (
            <button
              key={s}
              onClick={() => setFilter('sentiment', s)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                currentFilters.sentiment === s
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-accent',
              )}
            >
              {s === '' ? 'All' : s}
            </button>
          ))}
        </div>
      </div>

      {/* Urgency toggle */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Urgency
        </label>
        <div className="flex flex-wrap gap-1.5">
          {['', 'high', 'medium', 'low'].map((u) => (
            <button
              key={u}
              onClick={() => setFilter('urgency', u)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                currentFilters.urgency === u
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-accent',
              )}
            >
              {u === '' ? 'All' : u}
            </button>
          ))}
        </div>
      </div>

      {/* Language toggle */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-muted-foreground">
          Language
        </label>
        <div className="flex gap-1.5">
          {['', 'en', 'zh'].map((l) => (
            <button
              key={l}
              onClick={() => setFilter('language', l)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                currentFilters.language === l
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-accent',
              )}
            >
              {l === '' ? 'All' : l.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Date range */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="mb-1 block text-xs text-muted-foreground">From</label>
          <input
            type="date"
            value={currentFilters.from_date}
            onChange={(e) => setFilter('from_date', e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-muted-foreground">To</label>
          <input
            type="date"
            value={currentFilters.to_date}
            onChange={(e) => setFilter('to_date', e.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      {/* Footer: total + clear */}
      <div className="flex items-center justify-between border-t border-border pt-3">
        <span className="text-sm text-muted-foreground">
          {total !== undefined ? `${total.toLocaleString()} articles` : ''}
        </span>
        {activeCount > 0 && (
          <button onClick={clearAll} className="text-xs text-primary hover:underline">
            Clear filters ({activeCount})
          </button>
        )}
      </div>
    </div>
  )
}
