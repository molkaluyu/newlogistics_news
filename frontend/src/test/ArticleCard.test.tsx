import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ArticleCard } from '@/components/articles/ArticleCard'
import type { Article } from '@/api/articles'

const baseArticle: Article = {
  id: 'art-001',
  source_id: 'loadstar_rss',
  source_name: 'The Loadstar',
  url: 'https://theloadstar.com/article/test',
  title: 'Global shipping rates surge amid port congestion',
  summary_en: 'Container shipping rates have surged dramatically due to ongoing port congestion across major trade routes.',
  language: 'en',
  published_at: '2025-06-15T10:30:00Z',
  transport_modes: ['ocean'],
  primary_topic: 'rate_change',
  sentiment: 'negative',
  urgency: 'high',
  processing_status: 'completed',
}

function renderCard(article: Partial<Article> = {}) {
  return render(
    <MemoryRouter>
      <ArticleCard article={{ ...baseArticle, ...article }} />
    </MemoryRouter>,
  )
}

describe('ArticleCard', () => {
  it('renders the article title', () => {
    renderCard()
    expect(screen.getByText('Global shipping rates surge amid port congestion')).toBeInTheDocument()
  })

  it('links title to article detail page', () => {
    renderCard()
    const link = screen.getByText('Global shipping rates surge amid port congestion')
    expect(link.closest('a')?.getAttribute('href')).toBe('/articles/art-001')
  })

  it('renders source name', () => {
    renderCard()
    expect(screen.getByText('The Loadstar')).toBeInTheDocument()
  })

  it('renders summary text', () => {
    renderCard()
    expect(screen.getByText(/Container shipping rates have surged/)).toBeInTheDocument()
  })

  it('renders transport mode badge', () => {
    renderCard()
    expect(screen.getByText('ocean')).toBeInTheDocument()
  })

  it('renders sentiment badge', () => {
    renderCard()
    expect(screen.getByText('negative')).toBeInTheDocument()
  })

  it('renders urgency badge', () => {
    renderCard()
    expect(screen.getByText('high')).toBeInTheDocument()
  })

  it('renders primary topic badge', () => {
    renderCard()
    expect(screen.getByText('rate_change')).toBeInTheDocument()
  })

  it('renders language badge', () => {
    renderCard()
    expect(screen.getByText('EN')).toBeInTheDocument()
  })

  it('renders external link to original article', () => {
    renderCard()
    const externalLink = document.querySelector('a[target="_blank"]')
    expect(externalLink?.getAttribute('href')).toBe('https://theloadstar.com/article/test')
  })

  it('truncates long summaries', () => {
    const longSummary = 'A'.repeat(300)
    renderCard({ summary_en: longSummary })
    const text = screen.getByText(/A+\.\.\./)
    expect(text.textContent!.length).toBeLessThan(300)
  })

  it('uses summary_zh when summary_en is absent', () => {
    renderCard({ summary_en: undefined, summary_zh: '中文摘要' })
    expect(screen.getByText('中文摘要')).toBeInTheDocument()
  })

  it('renders multiple transport modes', () => {
    renderCard({ transport_modes: ['ocean', 'air'] })
    expect(screen.getByText('ocean')).toBeInTheDocument()
    expect(screen.getByText('air')).toBeInTheDocument()
  })
})
