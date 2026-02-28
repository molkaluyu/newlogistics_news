import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return '-'
  return new Date(date).toLocaleDateString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export function truncate(str: string, len: number): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '...'
}

export type SentimentType = 'positive' | 'negative' | 'neutral'
export type UrgencyType = 'high' | 'medium' | 'low'

export const sentimentColors: Record<SentimentType, string> = {
  positive: 'bg-green-100 text-green-800',
  negative: 'bg-red-100 text-red-800',
  neutral: 'bg-yellow-100 text-yellow-800',
}

export const urgencyColors: Record<UrgencyType, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-green-100 text-green-800',
}

export const transportIcons: Record<string, string> = {
  ocean: '\u{1F6A2}',
  air: '\u{2708}\u{FE0F}',
  road: '\u{1F69B}',
  rail: '\u{1F682}',
}
