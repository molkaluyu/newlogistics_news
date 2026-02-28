import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
} from 'recharts'
import { analyticsApi } from '@/api/analytics'
import { cn } from '@/lib/utils'

type TimeWindow = '24h' | '7d' | '30d'
type Granularity = 'hour' | 'day' | 'week'
type EntityType = 'companies' | 'ports' | 'people' | 'organizations'

function SectionSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-4 w-32 rounded bg-muted" />
      <div className="h-64 w-full rounded bg-muted" />
    </div>
  )
}

function SelectorButtons<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: T }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-border bg-muted/30 p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            value === opt.value
              ? 'bg-card text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function TrendingSection() {
  const [timeWindow, setTimeWindow] = useState<TimeWindow>('7d')

  const trendingQuery = useQuery({
    queryKey: ['analytics', 'trending', timeWindow],
    queryFn: () => analyticsApi.trending({ time_window: timeWindow, limit: 15 }),
  })

  const chartData = (trendingQuery.data ?? []).map((t) => ({
    topic: t.topic.length > 25 ? t.topic.slice(0, 22) + '...' : t.topic,
    count: t.count,
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold text-foreground">Trending Topics</h3>
        <SelectorButtons
          options={[
            { label: '24h', value: '24h' as TimeWindow },
            { label: '7d', value: '7d' as TimeWindow },
            { label: '30d', value: '30d' as TimeWindow },
          ]}
          value={timeWindow}
          onChange={setTimeWindow}
        />
      </div>

      {trendingQuery.isLoading ? (
        <SectionSkeleton />
      ) : trendingQuery.isError ? (
        <p className="text-sm text-red-600">Failed to load trending topics.</p>
      ) : chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={Math.max(chartData.length * 32, 200)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 5 }}>
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="topic"
              width={160}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                fontSize: '13px',
              }}
            />
            <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No trending topics for this time window.
        </p>
      )}
    </div>
  )
}

function SentimentSection() {
  const [granularity, setGranularity] = useState<Granularity>('day')

  const sentimentQuery = useQuery({
    queryKey: ['analytics', 'sentiment', granularity],
    queryFn: () => analyticsApi.sentimentTrend({ granularity, days: 30 }),
  })

  const chartData = (sentimentQuery.data ?? []).map((pt) => ({
    period: pt.period,
    positive: pt.positive,
    neutral: pt.neutral,
    negative: pt.negative,
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold text-foreground">Sentiment Trend</h3>
        <SelectorButtons
          options={[
            { label: 'Hourly', value: 'hour' as Granularity },
            { label: 'Daily', value: 'day' as Granularity },
            { label: 'Weekly', value: 'week' as Granularity },
          ]}
          value={granularity}
          onChange={setGranularity}
        />
      </div>

      {sentimentQuery.isLoading ? (
        <SectionSkeleton />
      ) : sentimentQuery.isError ? (
        <p className="text-sm text-red-600">Failed to load sentiment trend.</p>
      ) : chartData.length > 0 ? (
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={chartData} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="period"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) => {
                if (granularity === 'hour') return v.slice(11, 16)
                if (granularity === 'day') return v.slice(5, 10)
                return v.slice(0, 10)
              }}
            />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                borderRadius: '8px',
                border: '1px solid #e5e7eb',
                fontSize: '13px',
              }}
            />
            <Area
              type="monotone"
              dataKey="positive"
              stackId="1"
              stroke="#22c55e"
              fill="#bbf7d0"
            />
            <Area
              type="monotone"
              dataKey="neutral"
              stackId="1"
              stroke="#eab308"
              fill="#fef9c3"
            />
            <Area
              type="monotone"
              dataKey="negative"
              stackId="1"
              stroke="#ef4444"
              fill="#fecaca"
            />
          </AreaChart>
        </ResponsiveContainer>
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No sentiment data available.
        </p>
      )}
    </div>
  )
}

function EntitiesSection() {
  const [entityType, setEntityType] = useState<EntityType>('companies')

  const entitiesQuery = useQuery({
    queryKey: ['analytics', 'entities', entityType],
    queryFn: () => analyticsApi.entities({ entity_type: entityType, limit: 20 }),
  })

  const entities = entitiesQuery.data ?? []
  const maxCount = entities.length > 0 ? Math.max(...entities.map((e) => e.count), 1) : 1

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-lg font-semibold text-foreground">Top Entities</h3>
        <SelectorButtons
          options={[
            { label: 'Companies', value: 'companies' as EntityType },
            { label: 'Ports', value: 'ports' as EntityType },
            { label: 'People', value: 'people' as EntityType },
            { label: 'Organizations', value: 'organizations' as EntityType },
          ]}
          value={entityType}
          onChange={setEntityType}
        />
      </div>

      {entitiesQuery.isLoading ? (
        <SectionSkeleton />
      ) : entitiesQuery.isError ? (
        <p className="text-sm text-red-600">Failed to load entities.</p>
      ) : entities.length > 0 ? (
        <div className="space-y-2">
          {entities.map((entity, idx) => (
            <div key={entity.name} className="flex items-center gap-3">
              <span className="w-6 shrink-0 text-right text-xs font-medium text-muted-foreground">
                {idx + 1}
              </span>
              <div className="flex-1">
                <div className="mb-0.5 flex items-center justify-between text-sm">
                  <span className="truncate font-medium text-foreground">{entity.name}</span>
                  <span className="ml-2 shrink-0 text-xs text-muted-foreground">
                    {entity.count}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-purple-500 transition-all"
                    style={{ width: `${(entity.count / maxCount) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No entities found for this type.
        </p>
      )}
    </div>
  )
}

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Analytics</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Trends, sentiment analysis, and entity tracking
        </p>
      </div>

      <TrendingSection />
      <SentimentSection />
      <EntitiesSection />
    </div>
  )
}
