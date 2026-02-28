import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'positive' | 'negative' | 'warning' | 'info' | 'outline'
  className?: string
}

const variantClasses: Record<string, string> = {
  default: 'bg-gray-100 text-gray-800',
  positive: 'bg-green-100 text-green-800',
  negative: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  info: 'bg-blue-100 text-blue-800',
  outline: 'border border-border text-muted-foreground',
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function SentimentBadge({ sentiment }: { sentiment?: string }) {
  if (!sentiment) return null
  const variant = sentiment === 'positive' ? 'positive' : sentiment === 'negative' ? 'negative' : 'warning'
  return <Badge variant={variant}>{sentiment}</Badge>
}

export function UrgencyBadge({ urgency }: { urgency?: string }) {
  if (!urgency) return null
  const variant = urgency === 'high' ? 'negative' : urgency === 'medium' ? 'warning' : 'positive'
  return <Badge variant={variant}>{urgency}</Badge>
}

export function TransportBadge({ mode }: { mode: string }) {
  const icons: Record<string, string> = { ocean: '\u{1F6A2}', air: '\u{2708}\u{FE0F}', road: '\u{1F69B}', rail: '\u{1F682}' }
  return (
    <Badge variant="outline" className="gap-1">
      <span>{icons[mode] || ''}</span>
      {mode}
    </Badge>
  )
}
