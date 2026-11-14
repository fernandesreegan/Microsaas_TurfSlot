import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

export const OSM_TILE_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

/** Default blue marker (explicit so Vite bundles the images). */
export const defaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41],
})

/** Marker for the user's location / search centre. */
export const centerIcon = L.divIcon({
  className: '',
  html: '<span class="block size-4 rounded-full border-2 border-white bg-sky-500 shadow-md ring-4 ring-sky-500/30"></span>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
})

L.Marker.prototype.options.icon = defaultIcon

/** India-ish default view when nothing else is known. */
export const DEFAULT_CENTER: [number, number] = [20.5937, 78.9629]
export const DEFAULT_ZOOM = 5
