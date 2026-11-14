import { useState } from 'react'

import { CancelBookingDialog } from '@/components/bookings/CancelBookingDialog'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { StatusBadge } from '@/components/common/StatusBadge'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useOwnerBookings } from '@/hooks/useBookings'
import { bookingStatusStyles } from '@/lib/statusStyles'
import { formatInTurfTz, formatMoney } from '@/lib/format'
import { nativeFieldClass } from '@/lib/toastError'
import type { BookingStatus } from '@/types'

const STATUSES = Object.keys(bookingStatusStyles) as BookingStatus[]
const PAGE_SIZE = 20

function toStatus(value: string): BookingStatus | undefined {
  return STATUSES.find((s) => s === value)
}

export default function OwnerBookingsPage() {
  const [status, setStatus] = useState<BookingStatus | undefined>(undefined)
  const [page, setPage] = useState(1)
  const { data, isLoading, isError, error, refetch, isFetching } = useOwnerBookings({ status, page, page_size: PAGE_SIZE })
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <PageWrapper
      title="Bookings"
      actions={
        <select
          aria-label="Filter by status"
          className={`${nativeFieldClass} w-48`}
          value={status ?? ''}
          onChange={(e) => {
            setStatus(toStatus(e.target.value))
            setPage(1)
          }}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {bookingStatusStyles[s].label}
            </option>
          ))}
        </select>
      }
    >
      {isLoading ? (
        <LoadingSpinner className="py-10" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No bookings" />
      ) : (
        <>
          <div className="rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ref</TableHead>
                  <TableHead>Turf</TableHead>
                  <TableHead>Player</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell className="font-mono text-xs">{b.booking_ref}</TableCell>
                    <TableCell>{b.turf.name}</TableCell>
                    <TableCell>
                      <div>{b.player.full_name}</div>
                      <div className="text-xs text-muted-foreground">{b.player.email}</div>
                    </TableCell>
                    <TableCell>
                      {formatInTurfTz(b.start_at, b.turf.timezone, 'd MMM, HH:mm')}–
                      {formatInTurfTz(b.end_at, b.turf.timezone, 'HH:mm')}
                    </TableCell>
                    <TableCell>{formatMoney(b.total_amount, b.currency)}</TableCell>
                    <TableCell>
                      <StatusBadge status={b.status} />
                    </TableCell>
                    <TableCell>
                      <CancelBookingDialog booking={b} asOwner size="sm" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <div className="mt-4 flex items-center justify-center gap-3">
            <Button variant="outline" disabled={page <= 1 || isFetching} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button variant="outline" disabled={page >= totalPages || isFetching} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </>
      )}
    </PageWrapper>
  )
}
