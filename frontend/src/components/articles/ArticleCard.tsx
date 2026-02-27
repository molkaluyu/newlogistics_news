import { Link } from 'react-router-dom'
import { Clock, ExternalLink } from 'lucide-react'
import type { Article } from '@/api/articles'
import { Badge, SentimentBadge, UrgencyBadge, TransportBadge } from '@/components/common/Badge'
import { formatDate, truncate } from '@/lib/utils'

interface ArticleCardProps {
  article: Article
}

export function ArticleCard({ article }: ArticleCardProps) {
  const summary = article.summary_en || article.summary_zh || ''

  return (
    <article className="border-b border-border px-1 py-4 last:border-b-0">
      {/* Header row: title + external link */}
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/articles/${article.id}`}
          className="text-base font-semibold text-foreground hover:text-primary hover:underline"
        >
          {article.title}
        </Link>
        {article.url && (
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 flex-shrink-0 text-muted-foreground hover:text-foreground"
            title="Open original"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        )}
      </div>

      {/* Meta row: source, date, language */}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {article.source_name && <span className="font-medium">{article.source_name}</span>}
        {article.published_at && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(article.published_at)}
          </span>
        )}
        {article.language && (
          <Badge variant="outline">{article.language.toUpperCase()}</Badge>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {truncate(summary, 280)}
        </p>
      )}

      {/* Tags row: transport modes, topic, sentiment, urgency */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {article.transport_modes?.map((mode) => (
          <TransportBadge key={mode} mode={mode} />
        ))}
        {article.primary_topic && (
          <Badge variant="info">{article.primary_topic}</Badge>
        )}
        <SentimentBadge sentiment={article.sentiment} />
        <UrgencyBadge urgency={article.urgency} />
      </div>
    </article>
  )
}
