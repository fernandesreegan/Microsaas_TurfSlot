/** Forward geocoding via OpenStreetMap Nominatim (no API key; light, debounced use only). */

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'

export interface LatLng {
  lat: number
  lng: number
}

/** Raw Nominatim jsonv2 search result (only the fields we use). */
interface NominatimResult {
  display_name: string
  lat: string
  lon: string
}

export interface GeocodeResult extends LatLng {
  label: string
}

export const GEOCODE_MIN_CHARS = 3

export const geocodeService = {
  /** Search places by free text; returns up to 5 results. */
  async search(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
    const q = query.trim()
    if (q.length < GEOCODE_MIN_CHARS) return []
    const url = `${NOMINATIM_URL}?format=jsonv2&limit=5&q=${encodeURIComponent(q)}`
    const res = await fetch(url, { signal, headers: { Accept: 'application/json' } })
    if (!res.ok) throw new Error(`Location search failed (${res.status})`)
    const data = (await res.json()) as NominatimResult[]
    return data
      .map((r) => ({ label: r.display_name, lat: Number(r.lat), lng: Number(r.lon) }))
      .filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lng))
  },
}
