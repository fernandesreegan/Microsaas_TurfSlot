import type { BookingStatus } from './booking'
import type { UserRole } from './user'

export interface AdminStats {
  users_by_role: Record<UserRole, number>
  turfs_active: number
  bookings_by_status: Record<BookingStatus, number>
  /** minor units */
  gmv: number
  /** minor units */
  refunds: number
}

export interface AdminUserUpdate {
  is_active?: boolean
  role?: UserRole
}

export interface AdminTurfUpdate {
  is_active: boolean
}

export interface AdminUsersParams {
  role?: UserRole
  q?: string
  is_active?: boolean
  page?: number
  page_size?: number
}

export interface AdminTurfsParams {
  city?: string
  q?: string
  is_active?: boolean
  page?: number
  page_size?: number
}

export interface AdminBookingsParams {
  turf_id?: number
  status?: BookingStatus
  /** YYYY-MM-DD */
  date?: string
  page?: number
  page_size?: number
}
