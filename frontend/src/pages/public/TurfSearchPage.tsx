import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageSkeleton } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { TurfCard } from '@/components/turfs/TurfCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useTurfs } from '@/hooks/useTurfs'
import { humanize } from '@/lib/format'
import { nativeFieldClass } from '@/lib/toastError'
import { SPORT_TYPES, type SportType } from '@/types'

const PAGE_SIZE = 12

function toSport(value: string | null): SportType | undefined {
  return SPORT_TYPES.find((s) => s === value)
}

export default function TurfSearchPage() {
  const [params, setParams] = useSearchParams()
  const city = params.get('city') ?? ''
  const sport = toSport(params.get('sport'))
  const q = params.get('q') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)

  const [form, setForm] = useState({ city, sport: sport ?? '', q })
  const { data, isLoading, isError, error, refetch, isFetching } = useTurfs({
    city: city || undefined,
    sport,
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  })

  const update = (next: Record<string, string>): void => {
    const p = new URLSearchParams()
    Object.entries(next).forEach(([k, v]) => {
      if (v) p.set(k, v)
    })
    setParams(p)
  }

  const onSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault()
    update({ city: form.city.trim(), sport: form.sport, q: form.q.trim() })
  }

  const goToPage = (n: number): void => update({ city, sport: sport ?? '', q, page: String(n) })
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <PageWrapper title="Find a turf" description="Search by city, sport or name.">
      <form onSubmit={onSubmit} className="mb-6 grid gap-3 sm:grid-cols-4">
        <Input placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} aria-label="City" />
        <select
          className={nativeFieldClass}
          value={form.sport}
          onChange={(e) => setForm({ ...form, sport: e.target.value })}
          aria-label="Sport"
        >
          <option value="">Any sport</option>
          {SPORT_TYPES.map((s) => (
            <option key={s} value={s}>
              {humanize(s)}
            </option>
          ))}
        </select>
        <Input placeholder="Turf name" value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} aria-label="Search" />
        <Button type="submit">Search</Button>
      </form>

      {isLoading ? (
        <PageSkeleton variant="grid" className="px-0 sm:px-0 lg:px-0" />
      ) : isError ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No turfs found" description="Try a different city or sport." />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((turf) => (
              <TurfCard key={turf.id} turf={turf} />
            ))}
          </div>
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
        </>
      )}
    </PageWrapper>
  )
}
