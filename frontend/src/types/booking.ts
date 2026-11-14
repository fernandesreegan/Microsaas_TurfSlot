export type BookingStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'expired'
export type RefundStatus = 'none' | 'pending' | 'refunded' | 'failed'
export type CancelledBy = 'player' | 'owner' | 'admin' | 'system'
export type PaymentStatus = 'pending' | 'succeeded' | 'failed' | 'refunded' | 'refund_failed'

export interface BookingCreate {
  turf_id: number
  start_at: string
  slot_count: number
}

export interface BookingTurfSummary {
  id: number
  name: string
  slug: string
  city: string
  timezone: string
}

export interface BookingPlayerSummary {
  id: number
  full_name: string
  email: string
}

export interface BookingRead {
  id: number
  booking_ref: string
  turf: BookingTurfSummary
  player: BookingPlayerSummary
  start_at: string
  end_at: string
  slot_count: number
  /** minor units */
  total_amount: number
  currency: string
  status: BookingStatus
  hold_expires_at: string | null
  cancelled_by: string | null
  cancelled_at: string | null
  cancellation_reason: string | null
  refund_status: RefundStatus
  refund_eligible: boolean
  created_at: string
}

export interface BookingCheckout {
  booking: BookingRead
  checkout_url: string
}

export interface CancelRequest {
  reason?: string
}

export type BookingScope = 'upcoming' | 'past'

export interface MyBookingsParams {
  scope?: BookingScope
  status?: BookingStatus
  page?: number
  page_size?: number
}

export interface OwnerBookingsParams {
  turf_id?: number
  /** turf-local YYYY-MM-DD */
  date?: string
  status?: BookingStatus
  page?: number
  page_size?: number
}
