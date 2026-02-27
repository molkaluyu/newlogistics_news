import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Newspaper } from 'lucide-react'
import { articlesApi } from '@/api/articles'
import type { ArticleFilters as ArticleFiltersType } from '@/api/articles'
import { ArticleFilters } from '@/components/articles/ArticleFilters'
import { ArticleCard } from '@/components/articles/ArticleCard'
import { Pagination } from '@/components/common/Pagination'
import { ExportButton } from '@/components/common/ExportButton'

const PAGE_SIZE = 20

export default function FeedPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Build filters from URL search params
  const filters: ArticleFiltersType = {
    search: searchParams.get('search') || undefined,
    transport_mode: searchParams.get('transport_mode') || undefined,
    topic: searchParams.get('topic') || undefined,
    sentiment: searchParams.get('sentiment') || undefined,
    urgency: searchParams.get('urgency') || undefined,
    language: searchParams.get('language') || undefined,
    source_id: searchParams.get('source_id') || undefined,
    from_date: searchParams.get('from_date') || undefined,
    to_date: searchParams.get('to_date') || undefined,
    page: Number(searchParams.get('page')) || 1,
    page_size: PAGE_SIZE,
  }

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['articles', filters],
    queryFn: () => articlesApi.list(filters),
  })

  const handlePageChange = (page: number) => {
    const params = new URLSearchParams(searchParams)
    if (page > 1) params.set('page', String(page))
    else params.delete('page')
    setSearchParams(params)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">News Feed</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Browse and filter the latest logistics news
          </p>
        </div>
        <ExportButton filters={filters} />
      </div>

      {/* Content area: sidebar filters + article list */}
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left: Filters (sticky on desktop) */}
        <aside className="w-full flex-shrink-0 lg:sticky lg:top-20 lg:w-72 lg:self-start">
          <ArticleFilters total={data?.total} />
        </aside>

        {/* Right: Article list */}
        <main className="min-w-0 flex-1">
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {/* Error state */}
          {isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
              <p className="text-sm text-red-800">
                Failed to load articles: {error instanceof Error ? error.message : 'Unknown error'}
              </p>
            </div>
          )}

          {/* Empty state */}
          {data && data.articles.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Newspaper className="mb-3 h-12 w-12" />
              <p className="text-lg font-medium">No articles found</p>
              <p className="mt-1 text-sm">Try adjusting your filters or search terms</p>
            </div>
          )}

          {/* Article list */}
          {data && data.articles.length > 0 && (
            <div className="rounded-lg border border-border bg-card px-4">
              {data.articles.map((article) => (
                <ArticleCard key={article.id} article={article} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex justify-center pt-4">
              <Pagination
                page={data.page}
                pages={data.pages}
                onPageChange={handlePageChange}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
