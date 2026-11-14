import { Loader2, LocateFixed, MapPin } from 'lucide-react'
import { useEffect, useId, useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { GEOCODE_MIN_CHARS, geocodeService, type GeocodeResult } from '@/services/geocodeService'

const DEBOUNCE_MS = 400

export interface LocationSearchInputProps {
  /** Called with the chosen place (from a suggestion or the device location). */
  onSelect: (place: GeocodeResult) => void
  /** Initial text shown in the input (e.g. the current place label). */
  initialLabel?: string
  placeholder?: string
  /** Show the "Use my location" button. */
  showMyLocation?: boolean
  className?: string
}

/**
 * Text input with debounced Nominatim suggestions and an optional "Use my location" button.
 * `initialLabel` is read on mount only; pass a `key` to reset it.
 */
export function LocationSearchInput({
  onSelect,
  initialLabel = '',
  placeholder = 'Search area, city or landmark',
  showMyLocation = true,
  className,
}: LocationSearchInputProps) {
  const listId = useId()
  const [text, setText] = useState(initialLabel)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GeocodeResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [locating, setLocating] = useState(false)
  const [active, setActive] = useState(-1)

  useEffect(() => {
    const q = query.trim()
    if (q.length < GEOCODE_MIN_CHARS) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      geocodeService
        .search(q, controller.signal)
        .then((r) => {
          setResults(r)
          setActive(-1)
          setOpen(true)
        })
        .catch((err: unknown) => {
          if (!(err instanceof DOMException && err.name === 'AbortError')) setResults([])
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  const choose = (place: GeocodeResult): void => {
    setText(place.label)
    setQuery('')
    setResults([])
    setOpen(false)
    onSelect(place)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (!open || results.length === 0) {
      if (e.key === 'Enter') e.preventDefault()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (i + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      choose(results[Math.max(0, active)])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const locateMe = (): void => {
    if (!('geolocation' in navigator)) {
      toast.error('Location is not available in this browser')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false)
        choose({ label: 'My location', lat: pos.coords.latitude, lng: pos.coords.longitude })
      },
      (err) => {
        setLocating(false)
        toast.error('Could not get your location', { description: err.message })
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    )
  }

  return (
    <div className={cn('flex gap-2', className)}>
      <div className="relative flex-1">
        <MapPin className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <Input
          value={text}
          placeholder={placeholder}
          aria-label="Location"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          className="pr-8 pl-9"
          onChange={(e) => {
            const value = e.target.value
            setText(value)
            setQuery(value)
            const searchable = value.trim().length >= GEOCODE_MIN_CHARS
            setLoading(searchable)
            if (!searchable) {
              setResults([])
              setOpen(false)
            }
          }}
          onFocus={() => results.length > 0 && setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
        />
        {loading && (
          <Loader2 className="absolute top-1/2 right-3 size-4 -translate-y-1/2 animate-spin text-muted-foreground" aria-hidden="true" />
        )}
        {open && results.length > 0 && (
          <ul
            id={listId}
            role="listbox"
            className="absolute z-[1100] mt-1 max-h-72 w-full overflow-auto rounded-md border bg-popover p-1 text-sm text-popover-foreground shadow-lg"
          >
            {results.map((r, i) => (
              <li
                key={`${r.lat},${r.lng},${i}`}
                role="option"
                aria-selected={i === active}
                className={cn('cursor-pointer rounded px-2 py-1.5 hover:bg-accent', i === active && 'bg-accent')}
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(r)
                }}
              >
                {r.label}
              </li>
            ))}
          </ul>
        )}
      </div>
      {showMyLocation && (
        <Button type="button" variant="outline" onClick={locateMe} disabled={locating} aria-label="Use my location">
          {locating ? <Loader2 className="size-4 animate-spin" /> : <LocateFixed className="size-4" />}
          <span className="hidden sm:inline">Use my location</span>
        </Button>
      )}
    </div>
  )
}
