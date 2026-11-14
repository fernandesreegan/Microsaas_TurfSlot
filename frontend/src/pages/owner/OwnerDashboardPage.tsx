import { Link } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { StatusBadge } from '@/components/common/StatusBadge'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { useOwnerSummary } from '@/hooks/useBookings'
import { formatInTurfTz, formatMoney } from '@/lib/format'

interface StatCardProps {
  label: string
  value: string
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <GlassCard className="space-y-1">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </GlassCard>
  )
}

export default function OwnerDashboardPage() {
  const { data, isLoading, isError, error, refetch } = useOwnerSummary()

  if (isLoading) return <PageSkeleton variant="grid" rows={4} />
  if (isError || !data) {
    return (
      <PageWrapper title="Dashboard">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </PageWrapper>
    )
  }

  return (
    <PageWrapper title="Dashboard" description="Today at a glance.">
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Bookings today" value={String(data.bookings_today)} />
        <StatCard label="Revenue" value={formatMoney(data.revenue, data.currency)} />
        <StatCard label="Occupancy" value={`${Math.round(data.occupancy_pct)}%`} />
        <StatCard label="Cancellations" value={String(data.cancellations)} />
      </div>
      <h2 className="mb-3 text-xl font-semibold">Upcoming bookings</h2>
      {data.upcoming_bookings.length === 0 ? (
        <EmptyState title="No upcoming bookings" />
      ) : (
        <div className="space-y-2">
          {data.upcoming_bookings.map((b) => (
            <GlassCard key={b.id} hoverable={false} className="flex items-center justify-between gap-3 py-4">
              <div>
                <p className="font-medium">
                  {b.turf.name} · {b.player.full_name}
                </p>
                <p className="text-sm text-muted-foreground">
                  {formatInTurfTz(b.start_at, b.turf.timezone, 'EEE d MMM, HH:mm')} ·{' '}
                  {formatMoney(b.total_amount, b.currency)}
                </p>
              </div>
              <StatusBadge status={b.status} />
            </GlassCard>
          ))}
          <Link to="/owner/bookings" className="inline-block pt-2 text-sm text-primary hover:underline">
            View all bookings
          </Link>
        </div>
      )}
    </PageWrapper>
  )
}
