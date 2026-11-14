import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { GlassCard } from '@/components/ui/GlassCard'
import { useOwnerTurfs } from '@/hooks/useTurfs'
import { formatMoney, formatTimeHHMM } from '@/lib/format'

export default function OwnerTurfsPage() {
  const { data, isLoading, isError, error, refetch } = useOwnerTurfs()

  if (isLoading) return <PageSkeleton variant="grid" />

  return (
    <PageWrapper
      title="My turfs"
      actions={
        <Button asChild>
          <Link to="/owner/turfs/new">
            <Plus aria-hidden="true" /> New turf
          </Link>
        </Button>
      }
    >
      {isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <EmptyState title="No turfs yet" description="Create your first turf to start taking bookings." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((t) => (
            <GlassCard key={t.id} hoverable={false} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold">{t.name}</h3>
                <Badge variant={t.is_active ? 'default' : 'secondary'}>{t.is_active ? 'Active' : 'Inactive'}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{t.city}</p>
              <p className="text-sm">
                {formatTimeHHMM(t.opening_time)}–{formatTimeHHMM(t.closing_time)} · {t.slot_duration_minutes} min ·{' '}
                {formatMoney(t.base_price, t.currency)}
              </p>
              <div className="flex gap-3 pt-2 text-sm">
                <Link to={`/owner/turfs/${t.id}/edit`} className="text-primary hover:underline">
                  Edit
                </Link>
                <Link to={`/owner/turfs/${t.id}/calendar`} className="text-primary hover:underline">
                  Calendar
                </Link>
                <Link to={`/turfs/${t.slug}`} className="text-primary hover:underline">
                  View public page
                </Link>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </PageWrapper>
  )
}
