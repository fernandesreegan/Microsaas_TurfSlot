import type { BookingRead } from './booking'

export interface OwnerSummary {
  bookings_today: number
  upcoming_bookings: BookingRead[]
  occupancy_pct: number
  /** minor units */
  revenue: number
  /** minor units */
  refunds: number
  cancellations: number
  currency: string
}

export interface RevenuePoint {
  period_start: string
  /** minor units */
  revenue: number
  bookings: number
}

export type RevenueGroupBy = 'day' | 'week'

export interface OwnerSummaryParams {
  from?: string
  to?: string
  turf_id?: number
}

export interface RevenueParams {
  from?: string
  to?: string
  group_by?: RevenueGroupBy
  turf_id?: number
}
