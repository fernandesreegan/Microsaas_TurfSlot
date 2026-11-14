export type SportType = 'football' | 'cricket' | 'badminton' | 'tennis' | 'basketball' | 'pickleball' | 'other'

export const SPORT_TYPES: readonly SportType[] = [
  'football',
  'cricket',
  'badminton',
  'tennis',
  'basketball',
  'pickleball',
  'other',
]

export type SlotDurationMinutes = 30 | 60 | 90

export interface TurfRead {
  id: number
  slug: string
  name: string
  description: string
  address: string
  city: string
  latitude: number | null
  longitude: number | null
  timezone: string
  sport_types: SportType[]
  amenities: string[]
  image_urls: string[]
  slot_duration_minutes: SlotDurationMinutes
  /** HH:MM */
  opening_time: string
  /** HH:MM */
  closing_time: string
  /** minor units */
  base_price: number
  currency: string
  is_active: boolean
  owner_id: number
}

/** TurfRead minus id / slug / is_active / owner_id. */
export interface TurfCreate {
  name: string
  description: string
  address: string
  city: string
  latitude: number | null
  longitude: number | null
  timezone: string
  sport_types: SportType[]
  amenities: string[]
  image_urls: string[]
  slot_duration_minutes: SlotDurationMinutes
  /** HH:MM */
  opening_time: string
  /** HH:MM */
  closing_time: string
  /** minor units */
  base_price: number
  currency: string
}

export type TurfUpdate = Partial<TurfCreate>

export interface PricingRuleRead {
  id: number
  /** 0=Mon ... 6=Sun; null = every day */
  day_of_week: number | null
  /** HH:MM */
  start_time: string
  /** HH:MM */
  end_time: string
  /** minor units */
  price: number
  label: string
}

export type PricingRuleCreate = Omit<PricingRuleRead, 'id'>
export type PricingRuleUpdate = Partial<PricingRuleCreate>

/** GET /turfs/{id_or_slug} returns detail + pricing rules. */
export interface TurfDetail extends TurfRead {
  pricing_rules: PricingRuleRead[]
}

/** GET /turfs list item; `distance_km` is set only for location (lat/lng) searches. */
export interface TurfSearchItem extends TurfRead {
  distance_km?: number | null
}

export interface TurfSearchParams {
  city?: string
  /** search-center latitude (requires lng) */
  lat?: number
  /** search-center longitude (requires lat) */
  lng?: number
  /** 1..100, default 15 */
  radius_km?: number
  sport?: SportType
  q?: string
  /** turf-local YYYY-MM-DD */
  date?: string
  page?: number
  page_size?: number
}
