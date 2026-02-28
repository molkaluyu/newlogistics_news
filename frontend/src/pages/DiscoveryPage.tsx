import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Square,
  Search,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Eye,
  Radar,
  Zap,
  Globe,
  Rss,
  Loader2,
} from 'lucide-react'
import { discoveryApi } from '@/api/discovery'
import type { SourceCandidate, DiscoveryStatus, ProbeResult } from '@/api/discovery'
import { Badge } from '@/components/common/Badge'
import { cn, formatDate, truncate } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Small helper components
// ---------------------------------------------------------------------------

function ScoreBadge({ score, label }: { score: number | undefined | null; label: string }) {
  if (score == null) return <span className="text-xs text-muted-foreground">-</span>
  const color =
    score >= 75
      ? 'bg-green-100 text-green-800'
      : score >= 50
        ? 'bg-yellow-100 text-yellow-800'
        : 'bg-red-100 text-red-800'
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', color)}>
      {label}: {score}
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, 'info' | 'warning' | 'positive' | 'negative' | 'default'> = {
    discovered: 'info',
    validating: 'warning',
    validated: 'default',
    approved: 'positive',
    rejected: 'negative',
  }
  return <Badge variant={map[status] || 'default'}>{status}</Badge>
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  color: string
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-5">
      <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg', color)}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p className="text-xl font-bold text-foreground">{value}</p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Probe panel
// ---------------------------------------------------------------------------

function ProbePanel() {
  const [url, setUrl] = useState('')
  const probeMutation = useMutation({
    mutationFn: (probeUrl: string) => discoveryApi.probe(probeUrl),
  })

  const result = probeMutation.data as ProbeResult | undefined

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="text-lg font-semibold text-foreground mb-3">Probe URL</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Test any URL to check if it's a valid logistics news source.
      </p>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          onClick={() => url && probeMutation.mutate(url)}
          disabled={!url || probeMutation.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {probeMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Search className="h-4 w-4" />
          )}
          Probe
        </button>
      </div>

      {probeMutation.isError && (
        <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {(probeMutation.error as Error).message}
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant={result.reachable ? 'positive' : 'negative'}>
              {result.reachable ? 'Reachable' : 'Unreachable'}
            </Badge>
            {result.feed_url && <Badge variant="info">RSS Feed Found</Badge>}
            <ScoreBadge score={result.quality_score} label="Quality" />
            <ScoreBadge score={result.relevance_score} label="Relevance" />
            <ScoreBadge score={result.combined_score} label="Combined" />
          </div>

          {result.name && (
            <p className="text-sm">
              <span className="font-medium text-foreground">Site Name:</span>{' '}
              <span className="text-muted-foreground">{result.name}</span>
            </p>
          )}
          {result.feed_url && (
            <p className="text-sm">
              <span className="font-medium text-foreground">Feed URL:</span>{' '}
              <span className="text-muted-foreground break-all">{result.feed_url}</span>
            </p>
          )}

          {result.sample_articles && result.sample_articles.length > 0 && (
            <div>
              <p className="text-sm font-medium text-foreground mb-1">
                Sample Articles ({result.articles_fetched})
              </p>
              <div className="space-y-2">
                {result.sample_articles.map((a, i) => (
                  <div key={i} className="rounded-md border border-border bg-muted/30 p-3">
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      {a.title}
                    </a>
                    {a.body_preview && (
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                        {a.body_preview}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.fetch_error && (
            <p className="text-xs text-red-600">Error: {result.fetch_error}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Candidate row with expand
// ---------------------------------------------------------------------------

function CandidateRow({
  candidate,
  onApprove,
  onReject,
}: {
  candidate: SourceCandidate
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <tr className="border-b border-border hover:bg-muted/30">
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {candidate.feed_url ? (
              <Rss className="h-4 w-4 text-orange-500 shrink-0" />
            ) : (
              <Globe className="h-4 w-4 text-blue-500 shrink-0" />
            )}
            <div className="min-w-0">
              <p className="font-medium text-foreground truncate">{candidate.name || candidate.url}</p>
              <p className="text-xs text-muted-foreground truncate">{candidate.url}</p>
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground">{candidate.language || '-'}</td>
        <td className="px-4 py-3">
          <StatusBadge status={candidate.status} />
        </td>
        <td className="px-4 py-3">
          <ScoreBadge score={candidate.quality_score} label="Q" />
        </td>
        <td className="px-4 py-3">
          <ScoreBadge score={candidate.relevance_score} label="R" />
        </td>
        <td className="px-4 py-3 text-sm text-muted-foreground">{candidate.articles_fetched}</td>
        <td className="px-4 py-3 text-xs text-muted-foreground">{candidate.discovered_via || '-'}</td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setExpanded(!expanded)}
              className="rounded p-1 text-muted-foreground hover:text-foreground"
              title="View details"
            >
              <Eye className="h-4 w-4" />
            </button>
            {candidate.status !== 'approved' && candidate.status !== 'rejected' && (
              <>
                <button
                  onClick={() => onApprove(candidate.id)}
                  className="rounded p-1 text-green-600 hover:text-green-800"
                  title="Approve"
                >
                  <CheckCircle2 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => onReject(candidate.id)}
                  className="rounded p-1 text-red-600 hover:text-red-800"
                  title="Reject"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              </>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-muted/20">
          <td colSpan={8} className="px-4 py-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <p className="font-medium text-foreground mb-1">Discovery Info</p>
                <p className="text-muted-foreground">Via: {candidate.discovered_via || '-'}</p>
                <p className="text-muted-foreground">Query: {candidate.discovery_query || '-'}</p>
                <p className="text-muted-foreground">Feed: {candidate.feed_url || 'None'}</p>
                <p className="text-muted-foreground">
                  Created: {formatDate(candidate.created_at)}
                </p>
                {candidate.error_message && (
                  <p className="text-red-600 text-xs mt-1">Error: {candidate.error_message}</p>
                )}
              </div>
              <div>
                {candidate.sample_articles && candidate.sample_articles.length > 0 && (
                  <>
                    <p className="font-medium text-foreground mb-1">Sample Articles</p>
                    <div className="space-y-1">
                      {candidate.sample_articles.map((a, i) => (
                        <div key={i} className="text-xs">
                          <a
                            href={a.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                          >
                            {truncate(a.title, 80)}
                          </a>
                          {a.body_preview && (
                            <p className="text-muted-foreground line-clamp-1">{a.body_preview}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DiscoveryPage() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)

  // Queries
  const statusQuery = useQuery({
    queryKey: ['discovery', 'status'],
    queryFn: () => discoveryApi.status(),
    refetchInterval: 10_000,
  })

  const candidatesQuery = useQuery({
    queryKey: ['discovery', 'candidates', { status: statusFilter, page }],
    queryFn: () =>
      discoveryApi.candidates({
        status: statusFilter || undefined,
        page,
        page_size: 20,
        sort: 'created_at',
      }),
  })

  // Mutations
  const startMut = useMutation({
    mutationFn: () => discoveryApi.start(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })
  const stopMut = useMutation({
    mutationFn: () => discoveryApi.stop(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })
  const scanMut = useMutation({
    mutationFn: () => discoveryApi.scan(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })
  const validateMut = useMutation({
    mutationFn: () => discoveryApi.validate(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })
  const approveMut = useMutation({
    mutationFn: (id: string) => discoveryApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })
  const rejectMut = useMutation({
    mutationFn: (id: string) => discoveryApi.reject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['discovery'] }),
  })

  const status = statusQuery.data as DiscoveryStatus | undefined
  const data = candidatesQuery.data

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Source Discovery</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Automatically discover, validate, and add new logistics news sources
          </p>
        </div>
        <div className="flex items-center gap-2">
          {status?.running ? (
            <button
              onClick={() => stopMut.mutate()}
              disabled={stopMut.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          ) : (
            <button
              onClick={() => startMut.mutate()}
              disabled={startMut.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              Start
            </button>
          )}
        </div>
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          icon={Radar}
          label="Status"
          value={status?.running ? 'Running' : 'Stopped'}
          color={status?.running ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'}
        />
        <StatCard
          icon={Search}
          label="Discovered"
          value={status?.count_discovered ?? '...'}
          color="bg-blue-100 text-blue-600"
        />
        <StatCard
          icon={RefreshCw}
          label="Validating"
          value={(status?.count_validating ?? 0) + (status?.count_validated ?? 0)}
          color="bg-yellow-100 text-yellow-600"
        />
        <StatCard
          icon={CheckCircle2}
          label="Approved"
          value={status?.count_approved ?? '...'}
          color="bg-green-100 text-green-600"
        />
        <StatCard
          icon={XCircle}
          label="Rejected"
          value={status?.count_rejected ?? '...'}
          color="bg-red-100 text-red-600"
        />
      </div>

      {/* Manual actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => scanMut.mutate()}
          disabled={scanMut.isPending || status?.scan_in_progress}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          {scanMut.isPending || status?.scan_in_progress ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Radar className="h-4 w-4" />
          )}
          Run Scan Now
        </button>
        <button
          onClick={() => validateMut.mutate()}
          disabled={validateMut.isPending || status?.validate_in_progress}
          className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
        >
          {validateMut.isPending || status?.validate_in_progress ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Zap className="h-4 w-4" />
          )}
          Validate Pending
        </button>
        {status?.last_scan_at && (
          <span className="self-center text-xs text-muted-foreground">
            Last scan: {formatDate(status.last_scan_at)}
          </span>
        )}
      </div>

      {/* Probe panel */}
      <ProbePanel />

      {/* Candidates table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-foreground">Candidates</h3>
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="rounded-md border border-border bg-background px-3 py-1.5 text-sm text-foreground"
            >
              <option value="">All statuses</option>
              <option value="discovered">Discovered</option>
              <option value="validating">Validating</option>
              <option value="validated">Validated</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {candidatesQuery.isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Loading candidates...
          </div>
        ) : candidatesQuery.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Failed to load candidates.
          </div>
        ) : data && data.candidates.length > 0 ? (
          <>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-3">Source</th>
                    <th className="px-4 py-3">Lang</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Quality</th>
                    <th className="px-4 py-3">Relevance</th>
                    <th className="px-4 py-3">Articles</th>
                    <th className="px-4 py-3">Via</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.candidates.map((c) => (
                    <CandidateRow
                      key={c.id}
                      candidate={c}
                      onApprove={(id) => approveMut.mutate(id)}
                      onReject={(id) => rejectMut.mutate(id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data.pages > 1 && (
              <div className="mt-4 flex items-center justify-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-md border border-border px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {data.pages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page >= data.pages}
                  className="rounded-md border border-border px-3 py-1.5 text-sm disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
            <Radar className="h-12 w-12 mb-3 opacity-30" />
            <p>No candidates found. Run a discovery scan to get started.</p>
          </div>
        )}
      </div>
    </div>
  )
}
