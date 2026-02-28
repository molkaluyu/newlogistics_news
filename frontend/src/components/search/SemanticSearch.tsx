import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Loader2, Clock, ExternalLink } from 'lucide-react'
import type { Article } from '@/api/articles'
import { Badge, SentimentBadge, UrgencyBadge, TransportBadge } from '@/components/common/Badge'
import { formatDate, truncate, cn } from '@/lib/utils'

type SearchResult = Article & { similarity: number }

interface SemanticSearchProps {
  results: SearchResult[]
  isLoading: boolean
  onSearch: (query: string) => void
}

export function SemanticSearch({ results, isLoading, onSearch }: SemanticSearchProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (trimmed) onSearch(trimmed)
  }

  return (
    <div className="space-y-6">
      {/* Search form */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Describe what you're looking for, e.g. 'port congestion in Asia affecting container shipping rates'"
            className="w-full rounded-lg border border-border bg-background py-3 pl-12 pr-4 text-base placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          className="flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Search
        </button>
      </form>

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Searching across articles...</span>
          </div>
        </div>
      )}

      {/* Results */}
      {!isLoading && results.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">
            {results.length} result{results.length !== 1 ? 's' : ''} found
          </p>
          <div className="rounded-lg border border-border bg-card">
            {results.map((result, idx) => (
              <SearchResultCard key={result.id} result={result} rank={idx + 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SearchResultCard({ result, rank }: { result: SearchResult; rank: number }) {
  const similarityPct = Math.round(result.similarity * 100)
  const summary = result.summary_en || result.summary_zh || ''

  return (
    <article className="border-b border-border px-4 py-4 last:border-b-0">
      <div className="flex items-start gap-3">
        {/* Rank number */}
        <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-muted-foreground">
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          {/* Title + external link */}
          <div className="flex items-start justify-between gap-2">
            <Link
              to={`/articles/${result.id}`}
              className="text-base font-semibold text-foreground hover:text-primary hover:underline"
            >
              {result.title}
            </Link>
            {result.url && (
              <a
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-0.5 flex-shrink-0 text-muted-foreground hover:text-foreground"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>

          {/* Meta */}
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {result.source_name && (
              <span className="font-medium">{result.source_name}</span>
            )}
            {result.published_at && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatDate(result.published_at)}
              </span>
            )}
          </div>

          {/* Similarity bar */}
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  similarityPct >= 80
                    ? 'bg-green-500'
                    : similarityPct >= 60
                      ? 'bg-yellow-500'
                      : 'bg-orange-500',
                )}
                style={{ width: `${similarityPct}%` }}
              />
            </div>
            <span className="text-xs font-medium text-muted-foreground">
              {similarityPct}% match
            </span>
          </div>

          {/* Summary */}
          {summary && (
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              {truncate(summary, 250)}
            </p>
          )}

          {/* Badges */}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {result.transport_modes?.map((mode) => (
              <TransportBadge key={mode} mode={mode} />
            ))}
            {result.primary_topic && (
              <Badge variant="info">{result.primary_topic}</Badge>
            )}
            <SentimentBadge sentiment={result.sentiment} />
            <UrgencyBadge urgency={result.urgency} />
          </div>
        </div>
      </div>
    </article>
  )
}
