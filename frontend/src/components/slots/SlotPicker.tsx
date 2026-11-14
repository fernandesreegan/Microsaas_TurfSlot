import { addDays, format, parseISO } from 'date-fns'
import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { GradientButton } from '@/components/ui/GradientButton'
import { useCreateBooking } from '@/hooks/useBookings'
import { useAuth } from '@/hooks/useAuth'
import { useSlots } from '@/hooks/useTurfs'
import { env } from '@/lib/env'
import { formatInTurfTz, formatMoney, todayInTz } from '@/lib/format'
import { slotStatusClassNames } from '@/lib/statusStyles'
import { toastApiError } from '@/lib/toastError'
import { cn } from '@/lib/utils'
import type { TurfRead } from '@/types'

export interface SlotPickerProps {
  turf: TurfRead
}

interface Selection {
  start: number
  count: number
}

function nextDays(startDate: string, count: number): string[] {
  const base = parseISO(startDate)
  return Array.from({ length: count }, (_, i) => format(addDays(base, i), 'yyyy-MM-dd'))
}

export function SlotPicker({ turf }: SlotPickerProps) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const days = useMemo(() => nextDays(todayInTz(turf.timezone), 7), [turf.timezone])
  const [date, setDate] = useState<string>(days[0])
  const [selection, setSelection] = useState<Selection | null>(null)
  const slotsQuery = useSlots(turf.id, date)
  const createBooking = useCreateBooking()

  const slots = slotsQuery.data?.slots ?? []
  const currency = slotsQuery.data?.currency ?? turf.currency
  const max = env.maxSlotsPerBooking

  const selectedSlots = selection ? slots.slice(selection.start, selection.start + selection.count) : []
  const total = selectedSlots.reduce((sum, s) => sum + s.price, 0)

  const onPickDate = (d: string): void => {
    setDate(d)
    setSelection(null)
  }

  const onSlotClick = (i: number): void => {
    if (slots[i]?.status !== 'available') return
    if (!selection) {
      setSelection({ start: i, count: 1 })
      return
    }
    const end = selection.start + selection.count
    if (i >= selection.start && i < end) {
      setSelection(null)
    } else if (i === end && selection.count < max) {
      setSelection({ start: selection.start, count: selection.count + 1 })
    } else if (i === selection.start - 1 && selection.count < max) {
      setSelection({ start: i, count: selection.count + 1 })
    } else {
      setSelection({ start: i, count: 1 })
    }
  }

  const onBook = (): void => {
    if (!selection || selectedSlots.length === 0) return
    if (!user) {
      void navigate(`/login?next=${encodeURIComponent(location.pathname)}`)
      return
    }
    createBooking.mutate(
      { turf_id: turf.id, start_at: selectedSlots[0].start_at, slot_count: selectedSlots.length },
      {
        onSuccess: (data) => {
          void navigate(`/checkout/${data.booking.id}`)
        },
        onError: (err) => {
          toastApiError(err, 'Could not book these slots')
          setSelection(null)
          void slotsQuery.refetch()
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {days.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => onPickDate(d)}
            className={cn(
              'flex min-w-16 flex-col items-center rounded-xl border px-3 py-2 text-sm transition-colors',
              d === date ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
            )}
          >
            <span className="text-xs uppercase">{format(parseISO(d), 'EEE')}</span>
            <span className="text-lg font-semibold">{format(parseISO(d), 'd')}</span>
            <span className="text-xs">{format(parseISO(d), 'MMM')}</span>
          </button>
        ))}
      </div>

      {slotsQuery.isLoading ? (
        <LoadingSpinner className="py-10" />
      ) : slotsQuery.isError ? (
        <ErrorState error={slotsQuery.error} onRetry={() => void slotsQuery.refetch()} />
      ) : slots.length === 0 ? (
        <EmptyState title="No slots" description="This turf has no slots on the selected date." />
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {slots.map((slot, i) => {
            const selected = selection !== null && i >= selection.start && i < selection.start + selection.count
            return (
              <button
                key={slot.start_at}
                type="button"
                disabled={slot.status !== 'available'}
                onClick={() => onSlotClick(i)}
                aria-pressed={selected}
                className={cn(
                  'rounded-lg border px-2 py-2 text-sm transition-colors disabled:cursor-not-allowed',
                  slotStatusClassNames[slot.status],
                  selected && 'border-primary bg-primary text-primary-foreground hover:bg-primary',
                )}
              >
                <div className="font-medium">
                  {formatInTurfTz(slot.start_at, turf.timezone, 'HH:mm')} –{' '}
                  {formatInTurfTz(slot.end_at, turf.timezone, 'HH:mm')}
                </div>
                <div className="text-xs">
                  {slot.status === 'available' ? formatMoney(slot.price, currency) : slot.status}
                </div>
              </button>
            )
          })}
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-xl border bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm">
          {selectedSlots.length > 0 ? (
            <>
              <span className="font-medium">
                {selectedSlots.length} slot{selectedSlots.length > 1 ? 's' : ''}
              </span>{' '}
              · Total <span className="font-semibold">{formatMoney(total, currency)}</span>
            </>
          ) : (
            <span className="text-muted-foreground">
              Select up to {max} consecutive available slots.
            </span>
          )}
        </div>
        <GradientButton
          onClick={onBook}
          disabled={selectedSlots.length === 0}
          loading={createBooking.isPending}
          loadingText="Booking..."
        >
          Book now
        </GradientButton>
      </div>
    </div>
  )
}
