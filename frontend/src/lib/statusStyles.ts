import type { BookingStatus, RefundStatus, SlotStatus } from '@/types'

export interface StatusStyle {
  label: string
  className: string
}

export const bookingStatusStyles: Record<BookingStatus, StatusStyle> = {
  pending: {
    label: 'Pending payment',
    className: 'border-warning/40 bg-warning/15 text-amber-800 dark:text-amber-200',
  },
  confirmed: {
    label: 'Confirmed',
    className: 'border-success/40 bg-success/15 text-emerald-800 dark:text-emerald-200',
  },
  cancelled: {
    label: 'Cancelled',
    className: 'border-destructive/40 bg-destructive/10 text-destructive',
  },
  completed: {
    label: 'Completed',
    className: 'border-info/40 bg-info/15 text-sky-800 dark:text-sky-200',
  },
  expired: {
    label: 'Expired',
    className: 'border-border bg-muted text-muted-foreground',
  },
}

export const refundStatusStyles: Record<RefundStatus, StatusStyle> = {
  none: { label: 'No refund', className: 'border-border bg-muted text-muted-foreground' },
  pending: { label: 'Refund pending', className: 'border-warning/40 bg-warning/15 text-amber-800 dark:text-amber-200' },
  refunded: { label: 'Refunded', className: 'border-success/40 bg-success/15 text-emerald-800 dark:text-emerald-200' },
  failed: { label: 'Refund failed', className: 'border-destructive/40 bg-destructive/10 text-destructive' },
}

/** Tailwind classes per slot status — shared by SlotGrid / owner calendar. */
export const slotStatusClassNames: Record<SlotStatus, string> = {
  available: 'border-primary/40 bg-primary/10 text-primary hover:bg-primary/20',
  held: 'border-warning/40 bg-warning/15 text-amber-800 dark:text-amber-200',
  booked: 'border-destructive/30 bg-destructive/10 text-destructive',
  blocked: 'border-border bg-muted text-muted-foreground line-through',
  past: 'border-border bg-muted/40 text-muted-foreground/60',
}
