import { useQuery } from '@tanstack/react-query'
import { Newspaper, Radio, Clock, Activity } from 'lucide-react'
import { adminApi } from '@/api/admin'
import { analyticsApi } from '@/api/analytics'
import { articlesApi } from '@/api/articles'
import { cn, formatDate } from '@/lib/utils'
import { SentimentBadge } from '@/components/common/Badge'

function StatCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-border bg-card p-6">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-muted" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-20 rounded bg-muted" />
          <div className="h-6 w-16 rounded bg-muted" />
        </div>
      </div>
    </div>
  )
}

function TrendingBarSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse space-y-1">
          <div className="h-3 w-24 rounded bg-muted" />
          <div className="h-5 rounded bg-muted" style={{ width: `${80 - i * 12}%` }} />
        </div>
      ))}
    </div>
  )
}

function ArticleListSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse space-y-1 border-b border-border pb-3">
          <div className="h-4 w-3/4 rounded bg-muted" />
          <div className="flex gap-2">
            <div className="h-3 w-20 rounded bg-muted" />
            <div className="h-3 w-14 rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: () => adminApi.health(),
  })

  const trendingQuery = useQuery({
    queryKey: ['trending', { limit: 5 }],
    queryFn: () => analyticsApi.trending({ limit: 5 }),
  })

  const articlesQuery = useQuery({
    queryKey: ['articles', { page_size: 5 }],
    queryFn: () => articlesApi.list({ page_size: 5 }),
  })

  const health = healthQuery.data
  const maxTrendingCount = trendingQuery.data
    ? Math.max(...trendingQuery.data.map((t) => t.count), 1)
    : 1

  const statusColor =
    health?.status === 'ok'
      ? 'bg-green-500'
      : health?.status === 'degraded'
        ? 'bg-yellow-500'
        : 'bg-red-500'

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Dashboard</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Logistics news monitoring overview
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {healthQuery.isLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : healthQuery.isError ? (
          <div className="col-span-full rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
            Failed to load system health data. Please try again later.
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                  <Newspaper className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Total Articles</p>
                  <p className="text-2xl font-bold text-foreground">
                    {health?.article_count.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
                  <Radio className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Active Sources</p>
                  <p className="text-2xl font-bold text-foreground">
                    {health?.source_count}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600">
                  <Clock className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">Last Fetch</p>
                  <p className="text-sm font-semibold text-foreground">
                    {formatDate(health?.last_fetch_at)}
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">System Status</p>
                  <div className="flex items-center gap-2">
                    <span className={cn('inline-block h-2.5 w-2.5 rounded-full', statusColor)} />
                    <p className="text-lg font-bold capitalize text-foreground">
                      {health?.status ?? 'unknown'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Trending Topics */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">Trending Topics</h3>
          {trendingQuery.isLoading ? (
            <TrendingBarSkeleton />
          ) : trendingQuery.isError ? (
            <p className="text-sm text-red-600">Failed to load trending topics.</p>
          ) : trendingQuery.data && trendingQuery.data.length > 0 ? (
            <div className="space-y-3">
              {trendingQuery.data.slice(0, 5).map((topic) => (
                <div key={topic.topic}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="truncate font-medium text-foreground">{topic.topic}</span>
                    <span className="ml-2 shrink-0 text-muted-foreground">{topic.count}</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-blue-500 transition-all"
                      style={{ width: `${(topic.count / maxTrendingCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No trending topics yet.</p>
          )}
        </div>

        {/* Recent Articles */}
        <div className="rounded-xl border border-border bg-card p-6">
          <h3 className="mb-4 text-lg font-semibold text-foreground">Recent Articles</h3>
          {articlesQuery.isLoading ? (
            <ArticleListSkeleton />
          ) : articlesQuery.isError ? (
            <p className="text-sm text-red-600">Failed to load recent articles.</p>
          ) : articlesQuery.data && articlesQuery.data.articles.length > 0 ? (
            <div className="space-y-3">
              {articlesQuery.data.articles.slice(0, 5).map((article) => (
                <div
                  key={article.id}
                  className="border-b border-border pb-3 last:border-0 last:pb-0"
                >
                  <p className="text-sm font-medium leading-snug text-foreground line-clamp-2">
                    {article.title}
                  </p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{formatDate(article.published_at)}</span>
                    <SentimentBadge sentiment={article.sentiment} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No articles yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
