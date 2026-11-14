import L from 'leaflet'
import { useEffect } from 'react'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import { Link } from 'react-router'

import { formatDistance, formatMoney } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { LatLng } from '@/services/geocodeService'
import type { TurfSearchItem } from '@/types'

import { centerIcon, DEFAULT_CENTER, DEFAULT_ZOOM, defaultIcon, OSM_ATTRIBUTION, OSM_TILE_URL } from './leafletSetup'

export interface TurfMapProps {
  turfs: TurfSearchItem[]
  /** Optional search centre / user location marker. */
  center?: LatLng | null
  centerLabel?: string
  className?: string
  /** Zoom used when there is only one point to show. */
  singleZoom?: number
}

interface PlacedTurf {
  turf: TurfSearchItem
  position: [number, number]
}

function FitBounds({ points, singleZoom }: { points: [number, number][]; singleZoom: number }) {
  const map = useMap()
  const key = points.map((p) => p.join(',')).join(';')
  useEffect(() => {
    if (points.length === 0) return
    if (points.length === 1) {
      map.setView(points[0], singleZoom)
      return
    }
    map.fitBounds(L.latLngBounds(points), { padding: [32, 32], maxZoom: 15 })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures `points`
  }, [map, key, singleZoom])
  return null
}

/** OpenStreetMap map with a marker per turf (that has coordinates). */
export function TurfMap({ turfs, center, centerLabel, className, singleZoom = 14 }: TurfMapProps) {
  const placed: PlacedTurf[] = turfs
    .filter((t) => t.latitude != null && t.longitude != null)
    .map((t) => ({ turf: t, position: [Number(t.latitude), Number(t.longitude)] }))
  const points: [number, number][] = placed.map((p) => p.position)
  if (center) points.push([center.lat, center.lng])
  const initial: [number, number] = points[0] ?? DEFAULT_CENTER

  return (
    <div className={cn('isolate overflow-hidden rounded-xl border', className ?? 'h-[420px]')}>
      <MapContainer center={initial} zoom={points.length ? singleZoom : DEFAULT_ZOOM} scrollWheelZoom className="size-full">
        <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} />
        <FitBounds points={points} singleZoom={singleZoom} />
        {center && (
          <Marker position={[center.lat, center.lng]} icon={centerIcon}>
            <Popup>{centerLabel ?? 'Search location'}</Popup>
          </Marker>
        )}
        {placed.map(({ turf, position }) => (
          <Marker key={turf.id} position={position} icon={defaultIcon}>
            <Popup>
              <div className="space-y-1">
                <p className="font-semibold">{turf.name}</p>
                <p>
                  From {formatMoney(turf.base_price, turf.currency)}
                  {turf.distance_km != null && ` · ${formatDistance(turf.distance_km)} away`}
                </p>
                <Link to={`/turfs/${turf.slug}`} className="font-medium text-primary underline">
                  View turf
                </Link>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  )
}
