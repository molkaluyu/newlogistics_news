import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { articlesApi } from '@/api/articles'
import { ArticleDetail } from '@/components/articles/ArticleDetail'

export default function ArticlePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    data: article,
    isLoading: articleLoading,
    isError: articleError,
    error: articleErr,
  } = useQuery({
    queryKey: ['article', id],
    queryFn: () => articlesApi.get(id!),
    enabled: !!id,
  })

  const { data: relatedData } = useQuery({
    queryKey: ['related', id],
    queryFn: () => articlesApi.related(id!),
    enabled: !!id,
  })

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>

      {/* Loading state */}
      {articleLoading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {/* Error state */}
      {articleError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm text-red-800">
            Failed to load article:{' '}
            {articleErr instanceof Error ? articleErr.message : 'Unknown error'}
          </p>
          <button
            onClick={() => navigate('/feed')}
            className="mt-3 text-sm text-primary hover:underline"
          >
            Go to Feed
          </button>
        </div>
      )}

      {/* Article detail */}
      {article && (
        <ArticleDetail
          article={article}
          relatedArticles={relatedData?.related}
        />
      )}
    </div>
  )
}
