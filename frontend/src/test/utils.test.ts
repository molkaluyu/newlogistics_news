import { describe, it, expect } from 'vitest'
import { cn, formatDate, truncate, sentimentColors, urgencyColors, transportIcons } from '@/lib/utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('px-2', 'py-1')).toBe('px-2 py-1')
  })

  it('resolves tailwind conflicts', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden', 'extra')).toBe('base extra')
  })

  it('handles undefined/null', () => {
    expect(cn('base', undefined, null)).toBe('base')
  })
})

describe('formatDate', () => {
  it('returns "-" for null', () => {
    expect(formatDate(null)).toBe('-')
  })

  it('returns "-" for undefined', () => {
    expect(formatDate(undefined)).toBe('-')
  })

  it('returns "-" for empty string', () => {
    expect(formatDate('')).toBe('-')
  })

  it('formats a valid ISO date string', () => {
    const result = formatDate('2025-06-15T10:30:00Z')
    // Should contain year, month, day components
    expect(result).toContain('2025')
    expect(result).not.toBe('-')
  })
})

describe('truncate', () => {
  it('returns string unchanged when shorter than limit', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('returns string unchanged when equal to limit', () => {
    expect(truncate('hello', 5)).toBe('hello')
  })

  it('truncates and adds ellipsis when longer than limit', () => {
    expect(truncate('hello world', 5)).toBe('hello...')
  })

  it('handles empty string', () => {
    expect(truncate('', 5)).toBe('')
  })
})

describe('color maps', () => {
  it('sentimentColors has all three sentiments', () => {
    expect(sentimentColors).toHaveProperty('positive')
    expect(sentimentColors).toHaveProperty('negative')
    expect(sentimentColors).toHaveProperty('neutral')
  })

  it('urgencyColors has all three levels', () => {
    expect(urgencyColors).toHaveProperty('high')
    expect(urgencyColors).toHaveProperty('medium')
    expect(urgencyColors).toHaveProperty('low')
  })

  it('transportIcons has four modes', () => {
    expect(Object.keys(transportIcons)).toHaveLength(4)
    expect(transportIcons).toHaveProperty('ocean')
    expect(transportIcons).toHaveProperty('air')
    expect(transportIcons).toHaveProperty('road')
    expect(transportIcons).toHaveProperty('rail')
  })
})
