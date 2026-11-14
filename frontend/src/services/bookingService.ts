import type { BookingCheckout, BookingCreate, BookingRead, CancelRequest, MyBookingsParams, Page } from '@/types'

import { api } from './api'

const CHECKOUT_KEY_PREFIX = 'turfslot:checkout:'

function storeCheckoutUrl(id: number, url: string): void {
  try {
    sessionStorage.setItem(`${CHECKOUT_KEY_PREFIX}${id}`, url)
  } catch {
    // storage unavailable; checkout will be re-requested
  }
}

function getCheckoutUrl(id: number): string | null {
  try {
    return sessionStorage.getItem(`${CHECKOUT_KEY_PREFIX}${id}`)
  } catch {
    return null
  }
}

export const bookingService = {
  /** POST /bookings -> BookingCheckout (checkout_url is cached in sessionStorage). */
  async create(body: BookingCreate): Promise<BookingCheckout> {
    const { data } = await api.post<BookingCheckout>('/bookings', body)
    storeCheckoutUrl(data.booking.id, data.checkout_url)
    return data
  },

  /** POST /bookings/{id}/checkout -> fresh checkout session for a pending booking. */
  async checkout(id: number): Promise<BookingCheckout> {
    const { data } = await api.post<BookingCheckout>(`/bookings/${id}/checkout`)
    storeCheckoutUrl(id, data.checkout_url)
    return data
  },

  /** GET /bookings/me */
  async listMine(params: MyBookingsParams): Promise<Page<BookingRead>> {
    const { data } = await api.get<Page<BookingRead>>('/bookings/me', { params })
    return data
  },

  /** GET /bookings/{id} */
  async get(id: number): Promise<BookingRead> {
    const { data } = await api.get<BookingRead>(`/bookings/${id}`)
    return data
  },

  /** POST /bookings/{id}/cancel */
  async cancel(id: number, body: CancelRequest = {}): Promise<BookingRead> {
    const { data } = await api.post<BookingRead>(`/bookings/${id}/cancel`, body)
    return data
  },

  getCheckoutUrl,
}
