import { useState } from 'react'
import { toast } from 'sonner'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useCancelBooking } from '@/hooks/useBookings'
import { toastApiError } from '@/lib/toastError'
import type { BookingRead } from '@/types'

export interface CancelBookingDialogProps {
  booking: BookingRead
  /** Owner-side cancels always refund; show that instead of the player policy text. */
  asOwner?: boolean
  size?: 'sm' | 'default'
}

export function CancelBookingDialog({ booking, asOwner = false, size = 'default' }: CancelBookingDialogProps) {
  const [reason, setReason] = useState('')
  const cancel = useCancelBooking()

  if (booking.status !== 'confirmed' && booking.status !== 'pending') return null

  const refundText =
    booking.status === 'pending'
      ? 'This booking has not been paid, so no refund applies.'
      : asOwner || booking.refund_eligible
        ? 'A full refund will be issued to the original payment method.'
        : 'This booking is within the cancellation cutoff and is NOT eligible for a refund.'

  const onConfirm = (): void => {
    cancel.mutate(
      { id: booking.id, reason: reason.trim() || undefined },
      {
        onSuccess: () => toast.success('Booking cancelled'),
        onError: (err) => toastApiError(err, 'Could not cancel booking'),
      },
    )
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" size={size} disabled={cancel.isPending}>
          Cancel booking
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel booking {booking.booking_ref}?</AlertDialogTitle>
          <AlertDialogDescription>{refundText}</AlertDialogDescription>
        </AlertDialogHeader>
        <Textarea
          placeholder="Reason (optional)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
        />
        <AlertDialogFooter>
          <AlertDialogCancel>Keep booking</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={onConfirm}>
            Cancel booking
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
