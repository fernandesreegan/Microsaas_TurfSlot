import { useState } from 'react'
import { Link } from 'react-router'

import { BookingCard } from '@/components/bookings/BookingCard'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useMyBookings } from '@/hooks/useBookings'
import type { BookingScope } from '@/types'

export default function MyBookingsPage() {
  const [scope, setScope] = useState<BookingScope>('upcoming')
  const { data, isLoading, isError, error, refetch } = useMyBookings({ scope, page_size: 50 })

  return (
    <PageWrapper title="My bookings">
      <Tabs value={scope} onValueChange={(v) => setScope(v === 'past' ? 'past' : 'upcoming')} className="mb-4">
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
          <TabsTrigger value="past">Past</TabsTrigger>
        </TabsList>
      </Tabs>
      {isLoading ? (
        <LoadingSpinner className="py-10" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title={scope === 'upcoming' ? 'No upcoming bookings' : 'No past bookings'}
          action={
            <Link to="/turfs" className="font-medium text-primary hover:underline">
              Find a turf
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {data.items.map((b) => (
            <BookingCard key={b.id} booking={b} />
          ))}
        </div>
      )}
    </PageWrapper>
  )
}
