import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search as SearchIcon } from 'lucide-react'
import { articlesApi } from '@/api/articles'
import type { Article } from '@/api/articles'
import { SemanticSearch } from '@/components/search/SemanticSearch'

type SearchResult = Article & { similarity: number }

export default function SearchPage() {
  const [searchQuery, setSearchQuery] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['semantic-search', searchQuery],
    queryFn: () => articlesApi.semanticSearch(searchQuery),
    enabled: !!searchQuery,
  })

  const results: SearchResult[] = data?.results ?? []

  const handleSearch = (query: string) => {
    setSearchQuery(query)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Semantic Search</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Search articles using natural language queries powered by AI
        </p>
      </div>

      {/* Search component */}
      <SemanticSearch
        results={results}
        isLoading={isLoading}
        onSearch={handleSearch}
      />

      {/* Initial empty state (before any search) */}
      {!searchQuery && !isLoading && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <SearchIcon className="mb-3 h-12 w-12" />
          <p className="text-lg font-medium">Search the news</p>
          <p className="mt-1 max-w-md text-center text-sm">
            Enter a natural language query to find semantically related articles. Try things
            like &quot;container shipping delays in Europe&quot; or &quot;air freight rate
            increases&quot;.
          </p>
        </div>
      )}

      {/* No results state */}
      {searchQuery && !isLoading && results.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <SearchIcon className="mb-3 h-12 w-12" />
          <p className="text-lg font-medium">No results found</p>
          <p className="mt-1 text-sm">
            Try rephrasing your query or using different keywords
          </p>
        </div>
      )}
    </div>
  )
}
