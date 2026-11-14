import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { StatusBadge } from '@/components/common/StatusBadge'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { useBooking } from '@/hooks/useBookings'
import { formatInTurfTz, formatMoney } from '@/lib/format'
import { toastApiError } from '@/lib/toastError'
import { bookingService } from '@/services/bookingService'

function useSecondsLeft(expiresAt: string | null | undefined): number | null {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!expiresAt) return undefined
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [expiresAt])
  if (!expiresAt) return null
  return Math.max(0, Math.floor((new Date(expiresAt).getTime() - now) / 1000))
}

export default function CheckoutPage() {
  const { bookingId } = useParams()
  const id = Number(bookingId)
  const { data: booking, isLoading, isError, error, refetch } = useBooking(id)
  const secondsLeft = useSecondsLeft(booking?.status === 'pending' ? booking.hold_expires_at : null)
  const [redirecting, setRedirecting] = useState(false)

  if (isLoading) return <PageSkeleton rows={3} />
  if (isError || !booking) {
    return (
      <PageWrapper>
        <ErrorState error={error} onRetry={() => void refetch()} />
      </PageWrapper>
    )
  }

  const tz = booking.turf.timezone
  const expired = secondsLeft === 0

  const onPay = async (): Promise<void> => {
    setRedirecting(true)
    try {
      const url = bookingService.getCheckoutUrl(booking.id) ?? (await bookingService.checkout(booking.id)).checkout_url
      window.location.href = url
    } catch (err: unknown) {
      setRedirecting(false)
      toastApiError(err, 'Could not start payment')
    }
  }

  return (
    <PageWrapper title="Checkout" className="max-w-xl">
      <GlassCard hoverable={false} className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{booking.turf.name}</h2>
          <StatusBadge status={booking.status} />
        </div>
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-muted-foreground">Reference</dt>
          <dd>{booking.booking_ref}</dd>
          <dt className="text-muted-foreground">Date</dt>
          <dd>{formatInTurfTz(booking.start_at, tz, 'EEE, d MMM yyyy')}</dd>
          <dt className="text-muted-foreground">Time</dt>
          <dd>
            {formatInTurfTz(booking.start_at, tz, 'HH:mm')} – {formatInTurfTz(booking.end_at, tz, 'HH:mm')} (
            {booking.slot_count} slot{booking.slot_count > 1 ? 's' : ''})
          </dd>
          <dt className="text-muted-foreground">Total</dt>
          <dd className="font-semibold">{formatMoney(booking.total_amount, booking.currency)}</dd>
        </dl>

        {booking.status === 'pending' ? (
          <>
            {secondsLeft !== null && (
              <p className={expired ? 'text-sm text-destructive' : 'text-sm text-muted-foreground'}>
                {expired
                  ? 'Your hold has expired. Please pick the slots again.'
                  : `Slots held for ${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, '0')}`}
              </p>
            )}
            <GradientButton
              fullWidth
              disabled={expired}
              loading={redirecting}
              loadingText="Redirecting..."
              onClick={() => void onPay()}
            >
              Pay now
            </GradientButton>
          </>
        ) : (
          <Link to={`/bookings/${booking.id}`} className="block text-center font-medium text-primary hover:underline">
            View booking
          </Link>
        )}
      </GlassCard>
    </PageWrapper>
  )
}
