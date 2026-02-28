import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge, SentimentBadge, UrgencyBadge, TransportBadge } from '@/components/common/Badge'

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Test</Badge>)
    expect(screen.getByText('Test')).toBeInTheDocument()
  })

  it('applies default variant classes', () => {
    const { container } = render(<Badge>Default</Badge>)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-gray-100')
  })

  it('applies positive variant', () => {
    const { container } = render(<Badge variant="positive">Good</Badge>)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-green-100')
  })

  it('applies negative variant', () => {
    const { container } = render(<Badge variant="negative">Bad</Badge>)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-red-100')
  })

  it('applies custom className', () => {
    const { container } = render(<Badge className="my-custom">Custom</Badge>)
    const span = container.querySelector('span')
    expect(span?.className).toContain('my-custom')
  })
})

describe('SentimentBadge', () => {
  it('returns null for undefined sentiment', () => {
    const { container } = render(<SentimentBadge sentiment={undefined} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders positive sentiment', () => {
    render(<SentimentBadge sentiment="positive" />)
    expect(screen.getByText('positive')).toBeInTheDocument()
  })

  it('renders negative sentiment with red styling', () => {
    const { container } = render(<SentimentBadge sentiment="negative" />)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-red-100')
  })

  it('renders neutral sentiment with yellow styling', () => {
    const { container } = render(<SentimentBadge sentiment="neutral" />)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-yellow-100')
  })
})

describe('UrgencyBadge', () => {
  it('returns null for undefined urgency', () => {
    const { container } = render(<UrgencyBadge urgency={undefined} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders high urgency with red styling', () => {
    const { container } = render(<UrgencyBadge urgency="high" />)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-red-100')
    expect(screen.getByText('high')).toBeInTheDocument()
  })

  it('renders low urgency with green styling', () => {
    const { container } = render(<UrgencyBadge urgency="low" />)
    const span = container.querySelector('span')
    expect(span?.className).toContain('bg-green-100')
  })
})

describe('TransportBadge', () => {
  it('renders mode text', () => {
    render(<TransportBadge mode="ocean" />)
    expect(screen.getByText('ocean')).toBeInTheDocument()
  })

  it('renders ship icon for ocean', () => {
    render(<TransportBadge mode="ocean" />)
    expect(screen.getByText('\u{1F6A2}')).toBeInTheDocument()
  })

  it('renders plane icon for air', () => {
    render(<TransportBadge mode="air" />)
    expect(screen.getByText('\u{2708}\u{FE0F}')).toBeInTheDocument()
  })

  it('handles unknown mode gracefully', () => {
    render(<TransportBadge mode="unknown" />)
    expect(screen.getByText('unknown')).toBeInTheDocument()
  })
})
