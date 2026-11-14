import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { CancelBookingDialog } from '@/components/bookings/CancelBookingDialog'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingSpinner, PageSkeleton } from '@/components/common/LoadingSpinner'
import { RefundStatusBadge, StatusBadge } from '@/components/common/StatusBadge'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { useBooking } from '@/hooks/useBookings'
import { formatInTurfTz, formatMoney } from '@/lib/format'

const POLL_MS = 2000
const POLL_LIMIT_MS = 60_000

export default function BookingDetailPage() {
  const { id: idParam } = useParams()
  const [params] = useSearchParams()
  const id = Number(idParam)
  const [pollStart] = useState(() => Date.now())
  const [pollExpired, setPollExpired] = useState(false)

  useEffect(() => {
    const t = window.setTimeout(() => setPollExpired(true), Math.max(0, POLL_LIMIT_MS - (Date.now() - pollStart)))
    return () => window.clearTimeout(t)
  }, [pollStart])

  const { data: booking, isLoading, isError, error, refetch } = useBooking(id, {
    refetchInterval: (status) => (status === 'pending' && !pollExpired ? POLL_MS : false),
  })
  const isPending = booking?.status === 'pending'
  const polling = isPending && !pollExpired

  if (isLoading) return <PageSkeleton rows={3} />
  if (isError || !booking) {
    return (
      <PageWrapper>
        <ErrorState error={error} onRetry={() => void refetch()} />
      </PageWrapper>
    )
  }

  const tz = booking.turf.timezone

  return (
    <PageWrapper title={`Booking ${booking.booking_ref}`} className="max-w-xl">
      <GlassCard hoverable={false} className="space-y-4">
        {isPending && params.get('fake_checkout') === '1' && (
          <p className="rounded-lg border border-info/40 bg-info/10 p-3 text-sm">
            Dev mode: the fake payment gateway is active. Simulate payment via the backend fake-gateway webhook; this
            page updates automatically.
          </p>
        )}
        <div className="flex items-center justify-between">
          <Link to={`/turfs/${booking.turf.slug}`} className="text-lg font-semibold hover:underline">
            {booking.turf.name}
          </Link>
          <StatusBadge status={booking.status} />
        </div>
        {polling && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoadingSpinner size="sm" /> Waiting for payment confirmation...
          </div>
        )}
        {isPending && !polling && (
          <p className="text-sm text-muted-foreground">
            Payment not confirmed yet.{' '}
            <Link to={`/checkout/${booking.id}`} className="text-primary hover:underline">
              Go to checkout
            </Link>
          </p>
        )}
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-muted-foreground">Date</dt>
          <dd>{formatInTurfTz(booking.start_at, tz, 'EEE, d MMM yyyy')}</dd>
          <dt className="text-muted-foreground">Time</dt>
          <dd>
            {formatInTurfTz(booking.start_at, tz, 'HH:mm')} – {formatInTurfTz(booking.end_at, tz, 'HH:mm')}
          </dd>
          <dt className="text-muted-foreground">Slots</dt>
          <dd>{booking.slot_count}</dd>
          <dt className="text-muted-foreground">Total</dt>
          <dd className="font-semibold">{formatMoney(booking.total_amount, booking.currency)}</dd>
          <dt className="text-muted-foreground">Location</dt>
          <dd>{booking.turf.city}</dd>
          {booking.status === 'cancelled' && (
            <>
              <dt className="text-muted-foreground">Refund</dt>
              <dd>
                <RefundStatusBadge status={booking.refund_status} />
              </dd>
              {booking.cancellation_reason && (
                <>
                  <dt className="text-muted-foreground">Reason</dt>
                  <dd>{booking.cancellation_reason}</dd>
                </>
              )}
            </>
          )}
        </dl>
        <div className="flex justify-end">
          <CancelBookingDialog booking={booking} />
        </div>
      </GlassCard>
    </PageWrapper>
  )
}
