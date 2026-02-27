import { Link } from 'react-router-dom'
import {
  ExternalLink,
  Clock,
  Globe,
  BarChart3,
  AlertTriangle,
  TrendingUp,
  Tags,
} from 'lucide-react'
import type { Article } from '@/api/articles'
import {
  Badge,
  SentimentBadge,
  UrgencyBadge,
  TransportBadge,
} from '@/components/common/Badge'
import { formatDate } from '@/lib/utils'

interface ArticleDetailProps {
  article: Article
  relatedArticles?: Article[]
}

export function ArticleDetail({ article, relatedArticles }: ArticleDetailProps) {
  return (
    <div className="space-y-8">
      {/* Article header */}
      <header className="space-y-3">
        <h1 className="text-2xl font-bold leading-tight text-foreground lg:text-3xl">
          {article.title}
        </h1>

        {/* Meta row */}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
          {article.source_name && (
            <span className="font-medium text-foreground">{article.source_name}</span>
          )}
          {article.published_at && (
            <span className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              {formatDate(article.published_at)}
            </span>
          )}
          {article.language && (
            <span className="flex items-center gap-1">
              <Globe className="h-4 w-4" />
              {article.language.toUpperCase()}
            </span>
          )}
          {article.url && (
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-primary hover:underline"
            >
              <ExternalLink className="h-4 w-4" />
              Original source
            </a>
          )}
        </div>

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-2">
          {article.transport_modes?.map((mode) => (
            <TransportBadge key={mode} mode={mode} />
          ))}
          {article.primary_topic && (
            <Badge variant="info">{article.primary_topic}</Badge>
          )}
          {article.secondary_topics?.map((topic) => (
            <Badge key={topic} variant="default">
              {topic}
            </Badge>
          ))}
          {article.content_type && (
            <Badge variant="outline">{article.content_type}</Badge>
          )}
        </div>
      </header>

      {/* Article body */}
      <section className="rounded-lg border border-border bg-card p-6">
        {article.body_markdown ? (
          <div
            className="prose prose-sm max-w-none text-foreground prose-headings:text-foreground prose-a:text-primary prose-strong:text-foreground"
            dangerouslySetInnerHTML={{ __html: markdownToHtml(article.body_markdown) }}
          />
        ) : article.body_text ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {article.body_text}
          </div>
        ) : (
          <p className="text-sm italic text-muted-foreground">No article body available.</p>
        )}
      </section>

      {/* LLM Analysis Section */}
      {article.llm_processed && (
        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-foreground">AI Analysis</h2>

          {/* Summaries */}
          <div className="grid gap-4 md:grid-cols-2">
            {article.summary_en && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  English Summary
                </h3>
                <p className="text-sm leading-relaxed text-foreground">{article.summary_en}</p>
              </div>
            )}
            {article.summary_zh && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Chinese Summary
                </h3>
                <p className="text-sm leading-relaxed text-foreground">{article.summary_zh}</p>
              </div>
            )}
          </div>

          {/* Analysis grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Sentiment */}
            {article.sentiment && (
              <AnalysisCard
                icon={<BarChart3 className="h-4 w-4" />}
                label="Sentiment"
              >
                <SentimentBadge sentiment={article.sentiment} />
              </AnalysisCard>
            )}

            {/* Market Impact */}
            {article.market_impact && (
              <AnalysisCard
                icon={<TrendingUp className="h-4 w-4" />}
                label="Market Impact"
              >
                <span className="text-sm font-medium text-foreground">
                  {article.market_impact}
                </span>
              </AnalysisCard>
            )}

            {/* Urgency */}
            {article.urgency && (
              <AnalysisCard
                icon={<AlertTriangle className="h-4 w-4" />}
                label="Urgency"
              >
                <UrgencyBadge urgency={article.urgency} />
              </AnalysisCard>
            )}
          </div>

          {/* Entities */}
          {article.entities && Object.keys(article.entities).length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Tags className="h-4 w-4" />
                Extracted Entities
              </h3>
              <div className="space-y-2">
                {Object.entries(article.entities).map(([category, values]) => (
                  <div key={category} className="flex flex-wrap items-start gap-2">
                    <span className="mt-0.5 min-w-[100px] text-xs font-semibold uppercase text-muted-foreground">
                      {category}
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {values.map((v) => (
                        <Badge key={v} variant="outline">
                          {v}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Key Metrics */}
          {article.key_metrics && article.key_metrics.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">Key Metrics</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {article.key_metrics.map((metric, idx) => (
                  <div
                    key={idx}
                    className="flex items-baseline justify-between rounded-md bg-secondary px-3 py-2"
                  >
                    <span className="text-xs text-muted-foreground">{metric.type}</span>
                    <span className="text-sm font-semibold text-foreground">{metric.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Regions */}
          {article.regions && article.regions.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">Regions</h3>
              <div className="flex flex-wrap gap-1.5">
                {article.regions.map((region) => (
                  <Badge key={region} variant="default">
                    {region}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Related Articles */}
      {relatedArticles && relatedArticles.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground">Related Articles</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {relatedArticles.map((related) => (
              <Link
                key={related.id}
                to={`/articles/${related.id}`}
                className="group rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent"
              >
                <h3 className="text-sm font-medium text-foreground group-hover:text-primary">
                  {related.title}
                </h3>
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  {related.source_name && <span>{related.source_name}</span>}
                  {related.published_at && <span>{formatDate(related.published_at)}</span>}
                </div>
                {related.transport_modes && related.transport_modes.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {related.transport_modes.map((mode) => (
                      <TransportBadge key={mode} mode={mode} />
                    ))}
                  </div>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

/** Minimal analysis card wrapper */
function AnalysisCard({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-secondary text-muted-foreground">
        {icon}
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <div className="mt-0.5">{children}</div>
      </div>
    </div>
  )
}

/**
 * Very basic markdown-to-HTML conversion.
 * Handles paragraphs, bold, italic, links, headings, and line breaks.
 */
function markdownToHtml(md: string): string {
  return md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // Headings
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold + italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    // Paragraphs (double newlines)
    .replace(/\n\n+/g, '</p><p>')
    // Single newlines become <br>
    .replace(/\n/g, '<br/>')
    // Wrap in <p>
    .replace(/^/, '<p>')
    .replace(/$/, '</p>')
}
