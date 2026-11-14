import { Clock, MapPin } from 'lucide-react'
import { useParams } from 'react-router'

import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { SlotPicker } from '@/components/slots/SlotPicker'
import { Badge } from '@/components/ui/badge'
import { GlassCard } from '@/components/ui/GlassCard'
import { useTurf } from '@/hooks/useTurfs'
import { formatMoney, formatTimeHHMM, humanize } from '@/lib/format'

export default function TurfDetailPage() {
  const { slug } = useParams()
  const { data: turf, isLoading, isError, error, refetch } = useTurf(slug)

  if (isLoading) return <PageSkeleton rows={4} />
  if (isError || !turf) {
    return (
      <PageWrapper>
        <ErrorState title="Turf not found" error={error} onRetry={() => void refetch()} />
      </PageWrapper>
    )
  }

  return (
    <PageWrapper title={turf.name}>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-1">
          {turf.image_urls[0] && (
            <img src={turf.image_urls[0]} alt={turf.name} className="h-56 w-full rounded-2xl object-cover" />
          )}
          <GlassCard hoverable={false} className="space-y-3">
            <p className="flex items-start gap-2 text-sm">
              <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {turf.address}, {turf.city}
            </p>
            <p className="flex items-center gap-2 text-sm">
              <Clock className="size-4" aria-hidden="true" />
              {formatTimeHHMM(turf.opening_time)} – {formatTimeHHMM(turf.closing_time)} · {turf.slot_duration_minutes} min
              slots
            </p>
            <p className="text-sm font-medium">From {formatMoney(turf.base_price, turf.currency)} per slot</p>
            <div className="flex flex-wrap gap-1">
              {turf.sport_types.map((s) => (
                <Badge key={s}>{humanize(s)}</Badge>
              ))}
            </div>
            {turf.amenities.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {turf.amenities.map((a) => (
                  <Badge key={a} variant="outline">
                    {a}
                  </Badge>
                ))}
              </div>
            )}
            {turf.description && <p className="text-sm text-muted-foreground">{turf.description}</p>}
            {turf.pricing_rules.length > 0 && (
              <div className="space-y-1 text-sm">
                <p className="font-medium">Pricing</p>
                {turf.pricing_rules.map((r) => (
                  <p key={r.id} className="text-muted-foreground">
                    {r.label || 'Rule'}: {formatTimeHHMM(r.start_time)}–{formatTimeHHMM(r.end_time)} ·{' '}
                    {formatMoney(r.price, turf.currency)}
                  </p>
                ))}
              </div>
            )}
          </GlassCard>
        </div>
        <GlassCard hoverable={false} className="lg:col-span-2">
          <h2 className="mb-4 text-xl font-semibold">Pick your slots</h2>
          <SlotPicker turf={turf} />
        </GlassCard>
      </div>
    </PageWrapper>
  )
}
