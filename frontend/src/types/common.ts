/** Generic paginated response: `Page[T]` from the API contract. */
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** Common paging query params (defaults page=1, page_size=20, max 100). */
export interface PageParams {
  page?: number
  page_size?: number
}

/** Machine-readable error codes returned in `ApiError.code`. */
export type ApiErrorCode =
  | 'SLOT_UNAVAILABLE'
  | 'HOLD_EXPIRED'
  | 'NOT_OWNER'
  | 'EMAIL_TAKEN'
  | 'INVALID_CREDENTIALS'
  | 'EMAIL_NOT_VERIFIED'
  | 'OVERLAPPING_RULE'
  | 'OVERLAPPING_BLOCK'
  | 'BOOKING_CONFLICT_WITH_BLOCK'
  | 'INVALID_TRANSITION'
  | 'OUTSIDE_BOOKING_WINDOW'
  | 'OWN_TURF'

/** API error shape: `{ detail: string, code?: string }`. */
export interface ApiError {
  detail: string
  code?: string
  /** HTTP status (client-side enrichment; not part of the server payload). */
  status?: number
}

export interface HealthResponse {
  status: string
  db: string
}
