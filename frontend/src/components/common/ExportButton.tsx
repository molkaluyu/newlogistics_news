import { useState } from 'react'
import { Download } from 'lucide-react'
import type { ArticleFilters } from '@/api/articles'

interface ExportButtonProps {
  filters: ArticleFilters
}

export function ExportButton({ filters }: ExportButtonProps) {
  const [open, setOpen] = useState(false)

  const doExport = (format: 'csv' | 'json') => {
    const params = new URLSearchParams()
    params.set('format', format)
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== '' && v !== null && k !== 'page' && k !== 'page_size') {
        params.set(k, String(v))
      }
    })
    window.open(`/api/v1/export/articles?${params}`, '_blank')
    setOpen(false)
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
      >
        <Download className="h-4 w-4" />
        Export
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-20 mt-1 w-40 rounded-md border border-border bg-card py-1 shadow-lg">
            <button
              onClick={() => doExport('csv')}
              className="flex w-full items-center px-3 py-2 text-sm hover:bg-accent"
            >
              Export CSV
            </button>
            <button
              onClick={() => doExport('json')}
              className="flex w-full items-center px-3 py-2 text-sm hover:bg-accent"
            >
              Export JSON
            </button>
          </div>
        </>
      )}
    </div>
  )
}
