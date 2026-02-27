import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp, Server, CheckCircle2, AlertTriangle } from 'lucide-react'
import { sourcesApi } from '@/api/sources'
import type { SourceHealth, FetchLog } from '@/api/sources'
import { cn, formatDate, truncate } from '@/lib/utils'
import { Badge } from '@/components/common/Badge'

function HealthDot({ status }: { status: string }) {
  const color =
    status === 'healthy'
      ? 'bg-green-500'
      : status === 'degraded'
        ? 'bg-yellow-500'
        : 'bg-red-500'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn('inline-block h-2 w-2 rounded-full', color)} />
      <span className="capitalize">{status}</span>
    </span>
  )
}

function TypeBadge({ type }: { type: string }) {
  const variant =
    type === 'rss'
      ? 'info'
      : type === 'api'
        ? 'positive'
        : type === 'scraper'
          ? 'warning'
          : 'default'
  return <Badge variant={variant}>{type}</Badge>
}

function SuccessRate({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 90 ? 'text-green-600' : pct >= 70 ? 'text-yellow-600' : 'text-red-600'
  return <span className={cn('font-medium', color)}>{pct}%</span>
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === 'success'
      ? 'positive'
      : status === 'partial'
        ? 'warning'
        : 'negative'
  return <Badge variant={variant}>{status}</Badge>
}

function relativeTime(dateStr: string | undefined | null): string {
  if (!dateStr) return '-'
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function TableSkeleton({ rows, cols }: { rows: number; cols: number }) {
  return (
    <tbody>
      {Array.from({ length: rows }).map((_, ri) => (
        <tr key={ri} className="border-b border-border">
          {Array.from({ length: cols }).map((_, ci) => (
            <td key={ci} className="px-4 py-3">
              <div className="h-4 w-20 animate-pulse rounded bg-muted" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  )
}

function SourceHealthTable({ data }: { data: SourceHealth[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[800px] text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Type</th>
            <th className="px-4 py-3">Health</th>
            <th className="px-4 py-3">Success Rate</th>
            <th className="px-4 py-3">24h Articles</th>
            <th className="px-4 py-3">Avg Duration</th>
            <th className="px-4 py-3">Last Fetched</th>
            <th className="px-4 py-3">Alerts</th>
          </tr>
        </thead>
        <tbody>
          {data.map((source) => (
            <tr key={source.source_id} className="border-b border-border hover:bg-muted/30">
              <td className="px-4 py-3 font-medium text-foreground">{source.name}</td>
              <td className="px-4 py-3">
                <TypeBadge type={source.source_id.includes('rss') ? 'rss' : 'universal'} />
              </td>
              <td className="px-4 py-3">
                <HealthDot status={source.health_status} />
              </td>
              <td className="px-4 py-3">
                <SuccessRate rate={source.success_rate_24h} />
              </td>
              <td className="px-4 py-3 text-foreground">{source.total_articles_24h}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {source.avg_duration_ms > 0 ? `${Math.round(source.avg_duration_ms)}ms` : '-'}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {relativeTime(source.last_fetched_at)}
              </td>
              <td className="px-4 py-3">
                {source.alerts && source.alerts.length > 0 ? (
                  <span className="text-xs text-red-600">{source.alerts.join(', ')}</span>
                ) : (
                  <span className="text-xs text-muted-foreground">-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FetchLogsTable({ data }: { data: FetchLog[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[900px] text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-3">Source ID</th>
            <th className="px-4 py-3">Started At</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Found</th>
            <th className="px-4 py-3">New</th>
            <th className="px-4 py-3">Dedup</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Error</th>
          </tr>
        </thead>
        <tbody>
          {data.map((log) => (
            <tr key={log.id} className="border-b border-border hover:bg-muted/30">
              <td className="px-4 py-3 font-mono text-xs text-foreground">
                {truncate(log.source_id, 24)}
              </td>
              <td className="px-4 py-3 text-muted-foreground">{formatDate(log.started_at)}</td>
              <td className="px-4 py-3">
                <StatusBadge status={log.status} />
              </td>
              <td className="px-4 py-3 text-foreground">{log.articles_found}</td>
              <td className="px-4 py-3 text-foreground">{log.articles_new}</td>
              <td className="px-4 py-3 text-foreground">{log.articles_dedup}</td>
              <td className="px-4 py-3 text-muted-foreground">{log.duration_ms}ms</td>
              <td className="px-4 py-3 text-xs text-red-600">
                {log.error_message ? truncate(log.error_message, 60) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function SourcesPage() {
  const [logsOpen, setLogsOpen] = useState(false)

  const healthQuery = useQuery({
    queryKey: ['sources', 'health'],
    queryFn: () => sourcesApi.health(),
  })

  const logsQuery = useQuery({
    queryKey: ['sources', 'fetchLogs', { limit: 20 }],
    queryFn: () => sourcesApi.fetchLogs({ limit: 20 }),
    enabled: logsOpen,
  })

  const sources = healthQuery.data ?? []
  const totalSources = sources.length
  const healthySources = sources.filter((s) => s.health_status === 'healthy').length
  const unhealthySources = totalSources - healthySources

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Data Sources</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Monitor source health and fetch activity
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
            <Server className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Total Sources</p>
            <p className="text-xl font-bold text-foreground">
              {healthQuery.isLoading ? '...' : totalSources}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Healthy</p>
            <p className="text-xl font-bold text-green-600">
              {healthQuery.isLoading ? '...' : healthySources}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 text-red-600">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Unhealthy</p>
            <p className="text-xl font-bold text-red-600">
              {healthQuery.isLoading ? '...' : unhealthySources}
            </p>
          </div>
        </div>
      </div>

      {/* Source Health Table */}
      <div>
        <h3 className="mb-3 text-lg font-semibold text-foreground">Source Health</h3>
        {healthQuery.isLoading ? (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[800px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Health</th>
                  <th className="px-4 py-3">Success Rate</th>
                  <th className="px-4 py-3">24h Articles</th>
                  <th className="px-4 py-3">Avg Duration</th>
                  <th className="px-4 py-3">Last Fetched</th>
                  <th className="px-4 py-3">Alerts</th>
                </tr>
              </thead>
              <TableSkeleton rows={5} cols={8} />
            </table>
          </div>
        ) : healthQuery.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load source health data. Please try again later.
          </div>
        ) : sources.length > 0 ? (
          <SourceHealthTable data={sources} />
        ) : (
          <p className="text-sm text-muted-foreground">No sources configured.</p>
        )}
      </div>

      {/* Fetch Logs (collapsible) */}
      <div>
        <button
          type="button"
          onClick={() => setLogsOpen((v) => !v)}
          className="flex items-center gap-2 text-lg font-semibold text-foreground hover:text-foreground/80"
        >
          Fetch Logs
          {logsOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>

        {logsOpen && (
          <div className="mt-3">
            {logsQuery.isLoading ? (
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full min-w-[900px] text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      <th className="px-4 py-3">Source ID</th>
                      <th className="px-4 py-3">Started At</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Found</th>
                      <th className="px-4 py-3">New</th>
                      <th className="px-4 py-3">Dedup</th>
                      <th className="px-4 py-3">Duration</th>
                      <th className="px-4 py-3">Error</th>
                    </tr>
                  </thead>
                  <TableSkeleton rows={5} cols={8} />
                </table>
              </div>
            ) : logsQuery.isError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                Failed to load fetch logs.
              </div>
            ) : logsQuery.data && logsQuery.data.length > 0 ? (
              <FetchLogsTable data={logsQuery.data} />
            ) : (
              <p className="text-sm text-muted-foreground">No fetch logs available.</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
