import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  page: number
  pages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null

  const range = getPageRange(page, pages)

  return (
    <nav className="flex items-center gap-1" aria-label="Pagination">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-sm disabled:opacity-40 hover:bg-accent"
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      {range.map((p, i) =>
        p === '...' ? (
          <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground">...</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p as number)}
            className={cn(
              'flex h-8 min-w-8 items-center justify-center rounded-md px-2 text-sm',
              p === page
                ? 'bg-primary text-primary-foreground'
                : 'border border-border hover:bg-accent',
            )}
          >
            {p}
          </button>
        ),
      )}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pages}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-sm disabled:opacity-40 hover:bg-accent"
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  )
}

function getPageRange(current: number, total: number): (number | '...')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const result: (number | '...')[] = [1]
  if (current > 3) result.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    result.push(i)
  }
  if (current < total - 2) result.push('...')
  result.push(total)
  return result
}
