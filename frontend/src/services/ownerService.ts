import type { BookingRead, OwnerBookingsParams, OwnerSummary, OwnerSummaryParams, Page, TurfRead } from '@/types'

import { api } from './api'

function isPage<T>(value: T[] | Page<T>): value is Page<T> {
  return !Array.isArray(value) && Array.isArray(value.items)
}

export const ownerService = {
  /** GET /owner/turfs (accepts either a list or a Page). */
  async listTurfs(): Promise<TurfRead[]> {
    const { data } = await api.get<TurfRead[] | Page<TurfRead>>('/owner/turfs', { params: { page_size: 100 } })
    return isPage(data) ? data.items : data
  },

  /** GET /owner/bookings */
  async listBookings(params: OwnerBookingsParams): Promise<Page<BookingRead>> {
    const { data } = await api.get<Page<BookingRead>>('/owner/bookings', { params })
    return data
  },

  /** GET /owner/dashboard/summary */
  async getSummary(params: OwnerSummaryParams = {}): Promise<OwnerSummary> {
    const { data } = await api.get<OwnerSummary>('/owner/dashboard/summary', { params })
    return data
  },
}
