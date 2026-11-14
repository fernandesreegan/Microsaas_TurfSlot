import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { GradientButton } from '@/components/ui/GradientButton'
import { Input } from '@/components/ui/input'
import { humanize } from '@/lib/format'
import { nativeFieldClass } from '@/lib/toastError'
import { SPORT_TYPES } from '@/types'

export default function HomePage() {
  const navigate = useNavigate()
  const [city, setCity] = useState('')
  const [sport, setSport] = useState('')

  const onSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault()
    const params = new URLSearchParams()
    if (city.trim()) params.set('city', city.trim())
    if (sport) params.set('sport', sport)
    void navigate(`/turfs?${params.toString()}`)
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
          <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
            <Input placeholder="City (e.g. Bengaluru)" value={city} onChange={(e) => setCity(e.target.value)} aria-label="City" />
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
              Search
            </GradientButton>
          </form>
        </GlassCard>
      </section>
    </PageWrapper>
  )
}
