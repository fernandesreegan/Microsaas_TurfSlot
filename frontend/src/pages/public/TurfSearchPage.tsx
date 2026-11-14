import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { LocationSearchInput } from '@/components/map/LocationSearchInput'
import { TurfMap } from '@/components/map/TurfMap'
import { TurfCard } from '@/components/turfs/TurfCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useTurfs } from '@/hooks/useTurfs'
import { humanize } from '@/lib/format'
import { nativeFieldClass } from '@/lib/toastError'
import type { GeocodeResult, LatLng } from '@/services/geocodeService'
import { SPORT_TYPES, type SportType } from '@/types'

const PAGE_SIZE = 12
const RADIUS_OPTIONS = [5, 10, 15, 25, 50] as const
const DEFAULT_RADIUS = 15

function toSport(value: string | null): SportType | undefined {
  return SPORT_TYPES.find((s) => s === value)
}

function toCoord(value: string | null, limit: number): number | undefined {
  if (value === null || value.trim() === '') return undefined
  const n = Number(value)
  return Number.isFinite(n) && Math.abs(n) <= limit ? n : undefined
}

function toRadius(value: string | null): number {
  const n = Number(value)
  return Number.isFinite(n) && n >= 1 && n <= 100 ? n : DEFAULT_RADIUS
}

export default function TurfSearchPage() {
  const [params, setParams] = useSearchParams()
  const city = params.get('city') ?? ''
  const sport = toSport(params.get('sport'))
  const q = params.get('q') ?? ''
  const lat = toCoord(params.get('lat'), 90)
  const lng = toCoord(params.get('lng'), 180)
  const label = params.get('label') ?? ''
  const radius = toRadius(params.get('radius'))
  const page = Math.max(1, Number(params.get('page')) || 1)
  const center: LatLng | null = lat !== undefined && lng !== undefined ? { lat, lng } : null

  const [name, setName] = useState(q)
  const { data, isLoading, isError, error, refetch, isFetching } = useTurfs({
    city: city || undefined,
    sport,
    q: q || undefined,
    ...(center ? { lat: center.lat, lng: center.lng, radius_km: radius } : {}),
    page,
    page_size: PAGE_SIZE,
  })

  /** Merge `changes` into the URL params (empty string removes a key); resets the page. */
  const update = (changes: Record<string, string>, keepPage = false): void => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => {
      if (v) next.set(k, v)
      else next.delete(k)
    })
    if (!keepPage) next.delete('page')
    setParams(next)
  }

  const onPlace = (place: GeocodeResult): void => {
    update({
      lat: place.lat.toFixed(6),
      lng: place.lng.toFixed(6),
      label: place.label,
      radius: String(radius),
      city: '',
    })
  }

  const onNameSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault()
    update({ q: name.trim() })
  }

  const goToPage = (n: number): void => update({ page: String(n) }, true)
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  const items = data?.items ?? []

  const results = isLoading ? (
    <PageSkeleton variant="grid" className="px-0 sm:px-0 lg:px-0" />
  ) : isError ? (
    <ErrorState error={error} onRetry={() => void refetch()} />
  ) : items.length === 0 ? (
    center ? (
      <EmptyState
        title={`No turfs within ${radius} km`}
        description="Try a larger radius, another sport, or a different location."
      />
    ) : (
      <EmptyState title="No turfs found" description="Try a different location or sport." />
    )
  ) : (
    <>
      {center && (
        <p className="mb-3 text-sm text-muted-foreground">
          {data?.total} turf{data?.total === 1 ? '' : 's'} within {radius} km
          {label ? ` of ${label}` : ''}
        </p>
      )}
      <div className={center ? 'grid gap-4 sm:grid-cols-2' : 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3'}>
        {items.map((turf) => (
          <TurfCard key={turf.id} turf={turf} />
        ))}
      </div>
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button variant="outline" disabled={page <= 1 || isFetching} onClick={() => goToPage(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button variant="outline" disabled={page >= totalPages || isFetching} onClick={() => goToPage(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </>
  )

  return (
    <PageWrapper title="Find a turf" description="Search near an area, city or landmark — or use your location.">
      <div className="mb-6 space-y-3">
        <LocationSearchInput key={label} onSelect={onPlace} initialLabel={label} />
        <div className="grid gap-3 sm:grid-cols-3">
          <select
            className={nativeFieldClass}
            value={String(radius)}
            onChange={(e) => update({ radius: e.target.value })}
            aria-label="Radius"
            disabled={!center}
          >
            {RADIUS_OPTIONS.map((r) => (
              <option key={r} value={r}>
                Within {r} km
              </option>
            ))}
          </select>
          <select
            className={nativeFieldClass}
            value={sport ?? ''}
            onChange={(e) => update({ sport: e.target.value })}
            aria-label="Sport"
          >
            <option value="">Any sport</option>
            {SPORT_TYPES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </select>
          <form onSubmit={onNameSubmit} className="flex gap-2">
            <Input
              placeholder="Filter by turf name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="Turf name"
            />
            <Button type="submit" variant="secondary">
              Filter
            </Button>
          </form>
        </div>
        {center && (
          <Button variant="link" className="h-auto p-0" onClick={() => update({ lat: '', lng: '', label: '', radius: '' })}>
            Clear location
          </Button>
        )}
      </div>

      {center ? (
        <div className="flex flex-col gap-6 lg:flex-row-reverse">
          <div className="lg:sticky lg:top-20 lg:w-1/2 lg:self-start">
            <TurfMap turfs={items} center={center} centerLabel={label || 'Search location'} className="h-[320px] lg:h-[560px]" />
          </div>
          <div className="lg:w-1/2">{results}</div>
        </div>
      ) : (
        results
      )}
    </PageWrapper>
  )
}
