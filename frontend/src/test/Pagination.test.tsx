import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '@/components/common/Pagination'

describe('Pagination', () => {
  it('returns null when pages <= 1', () => {
    const { container } = render(
      <Pagination page={1} pages={1} onPageChange={() => {}} />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders all page buttons for small page count', () => {
    render(<Pagination page={1} pages={5} onPageChange={() => {}} />)
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('highlights the current page', () => {
    render(<Pagination page={3} pages={5} onPageChange={() => {}} />)
    const btn = screen.getByText('3')
    expect(btn.className).toContain('bg-primary')
  })

  it('disables previous button on first page', () => {
    render(<Pagination page={1} pages={5} onPageChange={() => {}} />)
    const buttons = screen.getAllByRole('button')
    // First button is "previous"
    expect(buttons[0]).toBeDisabled()
  })

  it('disables next button on last page', () => {
    render(<Pagination page={5} pages={5} onPageChange={() => {}} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons[buttons.length - 1]).toBeDisabled()
  })

  it('calls onPageChange when a page button is clicked', () => {
    const handler = vi.fn()
    render(<Pagination page={1} pages={5} onPageChange={handler} />)
    fireEvent.click(screen.getByText('3'))
    expect(handler).toHaveBeenCalledWith(3)
  })

  it('calls onPageChange with page-1 for previous button', () => {
    const handler = vi.fn()
    render(<Pagination page={3} pages={5} onPageChange={handler} />)
    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[0])
    expect(handler).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange with page+1 for next button', () => {
    const handler = vi.fn()
    render(<Pagination page={3} pages={5} onPageChange={handler} />)
    const buttons = screen.getAllByRole('button')
    fireEvent.click(buttons[buttons.length - 1])
    expect(handler).toHaveBeenCalledWith(4)
  })

  it('shows ellipsis for large page counts', () => {
    render(<Pagination page={5} pages={20} onPageChange={() => {}} />)
    const ellipses = screen.getAllByText('...')
    expect(ellipses.length).toBeGreaterThanOrEqual(1)
  })
})
