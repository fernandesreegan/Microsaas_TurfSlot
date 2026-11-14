import { MapPin } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { GlassCard } from '@/components/ui/GlassCard'
import { formatMoney, humanize } from '@/lib/format'
import type { TurfRead } from '@/types'

export interface TurfCardProps {
  turf: TurfRead
}

export function TurfCard({ turf }: TurfCardProps) {
  const image = turf.image_urls[0]
  return (
    <Link to={`/turfs/${turf.slug}`} className="block">
      <GlassCard noPadding className="h-full overflow-hidden">
        {image ? (
          <img src={image} alt={turf.name} className="h-40 w-full object-cover" loading="lazy" />
        ) : (
          <div className="h-40 w-full bg-linear-to-br from-brand-from via-brand-via to-brand-to opacity-80" />
        )}
        <div className="space-y-2 p-4">
          <h3 className="text-lg font-semibold">{turf.name}</h3>
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="size-4" aria-hidden="true" />
            {turf.city}
          </p>
          <div className="flex flex-wrap gap-1">
            {turf.sport_types.map((s) => (
              <Badge key={s} variant="secondary">
                {humanize(s)}
              </Badge>
            ))}
          </div>
          <p className="text-sm font-medium">
            From {formatMoney(turf.base_price, turf.currency)} / {turf.slot_duration_minutes} min
          </p>
        </div>
      </GlassCard>
    </Link>
  )
}
