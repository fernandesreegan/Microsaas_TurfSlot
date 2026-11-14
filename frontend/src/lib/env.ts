function parsePositiveInt(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === '') return fallback
  const n = Number.parseInt(value, 10)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, '')
}

export interface AppEnv {
  /** Backend origin without trailing slash, e.g. http://localhost:8000 */
  apiUrl: string
  /** Full API base: `${apiUrl}/api/v1` */
  apiBaseUrl: string
  /** Max consecutive slots per booking (default 4). */
  maxSlotsPerBooking: number
}

const apiUrl = stripTrailingSlash(import.meta.env.VITE_API_URL ?? 'http://localhost:8000')

export const env: AppEnv = {
  apiUrl,
  apiBaseUrl: `${apiUrl}/api/v1`,
  maxSlotsPerBooking: parsePositiveInt(import.meta.env.VITE_MAX_SLOTS_PER_BOOKING, 4),
}
