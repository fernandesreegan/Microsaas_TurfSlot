import type { LeafletEventHandlerFnMap, Marker as LeafletMarker } from 'leaflet'
import { useEffect, useMemo } from 'react'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'

import { cn } from '@/lib/utils'
import type { LatLng } from '@/services/geocodeService'

import { DEFAULT_CENTER, DEFAULT_ZOOM, defaultIcon, OSM_ATTRIBUTION, OSM_TILE_URL } from './leafletSetup'

export interface LocationPickerProps {
  value: LatLng | null
  onChange: (value: LatLng) => void
  /** Pan here (e.g. after an address search) without moving the pin. */
  focus?: LatLng | null
  className?: string
}

const round6 = (n: number): number => Math.round(n * 1e6) / 1e6

function ClickHandler({ onChange }: { onChange: (value: LatLng) => void }) {
  useMapEvents({
    click: (e) => onChange({ lat: round6(e.latlng.lat), lng: round6(e.latlng.lng) }),
  })
  return null
}

function Recenter({ target }: { target: LatLng | null | undefined }) {
  const map = useMap()
  const lat = target?.lat
  const lng = target?.lng
  useEffect(() => {
    if (lat === undefined || lng === undefined) return
    map.setView([lat, lng], Math.max(map.getZoom(), 15))
  }, [map, lat, lng])
  return null
}

/** Click the map (or drag the pin) to choose a single location. */
export function LocationPicker({ value, onChange, focus, className }: LocationPickerProps) {
  const handlers = useMemo<LeafletEventHandlerFnMap>(
    () => ({
      dragend: (e) => {
        const pos = (e.target as LeafletMarker).getLatLng()
        onChange({ lat: round6(pos.lat), lng: round6(pos.lng) })
      },
    }),
    [onChange],
  )
  const start: [number, number] = value ? [value.lat, value.lng] : DEFAULT_CENTER

  return (
    <div className={cn('isolate overflow-hidden rounded-xl border', className ?? 'h-[320px]')}>
      <MapContainer center={start} zoom={value ? 15 : DEFAULT_ZOOM} scrollWheelZoom className="size-full cursor-crosshair">
        <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} />
        <ClickHandler onChange={onChange} />
        <Recenter target={focus ?? value} />
        {value && <Marker position={[value.lat, value.lng]} icon={defaultIcon} draggable eventHandlers={handlers} />}
      </MapContainer>
    </div>
  )
}
