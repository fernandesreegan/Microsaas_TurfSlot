import { Badge } from '@/components/ui/badge'
import { bookingStatusStyles, refundStatusStyles } from '@/lib/statusStyles'
import { cn } from '@/lib/utils'
import type { BookingStatus, RefundStatus } from '@/types'

export interface StatusBadgeProps {
  status: BookingStatus
  className?: string
}

/** Colored pill for a BookingStatus. */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const style = bookingStatusStyles[status]
  return (
    <Badge variant="outline" className={cn('rounded-full font-medium', style.className, className)}>
      {style.label}
    </Badge>
  )
}

/** Colored pill for a RefundStatus. */
export function RefundStatusBadge({ status, className }: { status: RefundStatus; className?: string }) {
  const style = refundStatusStyles[status]
  return (
    <Badge variant="outline" className={cn('rounded-full font-medium', style.className, className)}>
      {style.label}
    </Badge>
  )
}
