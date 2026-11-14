export type SlotStatus = 'available' | 'held' | 'booked' | 'blocked' | 'past'

export interface SlotRead {
  start_at: string
  end_at: string
  status: SlotStatus
  /** minor units */
  price: number
}

export interface DaySlots {
  turf_id: number
  /** turf-local YYYY-MM-DD */
  date: string
  timezone: string
  currency: string
  slots: SlotRead[]
}

export interface BlockedSlotCreate {
  start_at: string
  end_at: string
  reason?: string
}

export interface BlockedSlotRead {
  id: number
  turf_id: number
  start_at: string
  end_at: string
  reason: string | null
  created_by: number
  created_at: string
}
