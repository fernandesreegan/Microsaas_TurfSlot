import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { PageWrapper } from '@/components/layout/PageWrapper'
import { LocationSearchInput } from '@/components/map/LocationSearchInput'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { humanize } from '@/lib/format'
import { nativeFieldClass } from '@/lib/toastError'
import type { GeocodeResult } from '@/services/geocodeService'
import { SPORT_TYPES } from '@/types'

export default function HomePage() {
  const navigate = useNavigate()
  const [sport, setSport] = useState('')

  const search = (place: GeocodeResult | null): void => {
    const params = new URLSearchParams()
    if (place) {
      params.set('lat', place.lat.toFixed(6))
      params.set('lng', place.lng.toFixed(6))
      params.set('label', place.label)
      params.set('radius', '15')
    }
    if (sport) params.set('sport', sport)
    void navigate(`/turfs?${params.toString()}`)
  }

  const onSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault()
    search(null)
  }

  return (
    <PageWrapper title="Book your next game">
      <section className="mx-auto max-w-3xl space-y-6 py-12 text-center">
        <h2 className="bg-linear-to-r from-brand-from via-brand-via to-brand-to bg-clip-text text-4xl font-extrabold text-transparent sm:text-5xl">
          Find a turf. Pick a slot. Play.
        </h2>
        <p className="text-lg text-muted-foreground">
          Real-time availability and instant confirmation for football, cricket, badminton and more.
        </p>
        <GlassCard hoverable={false}>
          <LocationSearchInput onSelect={search} className="mb-3 text-left" />
          <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
            <select
              className={nativeFieldClass}
              value={sport}
              onChange={(e) => setSport(e.target.value)}
              aria-label="Sport"
            >
              <option value="">Any sport</option>
              {SPORT_TYPES.map((s) => (
                <option key={s} value={s}>
                  {humanize(s)}
                </option>
              ))}
            </select>
            <GradientButton type="submit" size="default">
              Browse all turfs
            </GradientButton>
          </form>
        </GlassCard>
      </section>
    </PageWrapper>
  )
}
