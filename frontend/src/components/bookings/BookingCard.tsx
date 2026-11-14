import { Link } from 'react-router'

import { StatusBadge } from '@/components/common/StatusBadge'
import { GlassCard } from '@/components/ui/GlassCard'
import { formatInTurfTz, formatMoney } from '@/lib/format'
import type { BookingRead } from '@/types'

import { CancelBookingDialog } from './CancelBookingDialog'

export interface BookingCardProps {
  booking: BookingRead
}

export function BookingCard({ booking }: BookingCardProps) {
  const tz = booking.turf.timezone
  return (
    <GlassCard hoverable={false} className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Link to={`/bookings/${booking.id}`} className="font-semibold hover:underline">
            {booking.turf.name}
          </Link>
          <StatusBadge status={booking.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          {formatInTurfTz(booking.start_at, tz, 'EEE, d MMM yyyy · HH:mm')} – {formatInTurfTz(booking.end_at, tz, 'HH:mm')}{' '}
          · {booking.turf.city}
        </p>
        <p className="text-sm">
          {booking.booking_ref} · {formatMoney(booking.total_amount, booking.currency)}
        </p>
      </div>
      <div className="flex gap-2">
        {booking.status === 'pending' && (
          <Link to={`/checkout/${booking.id}`} className="text-sm font-medium text-primary hover:underline">
            Complete payment
          </Link>
        )}
        <CancelBookingDialog booking={booking} size="sm" />
      </div>
    </GlassCard>
  )
}
