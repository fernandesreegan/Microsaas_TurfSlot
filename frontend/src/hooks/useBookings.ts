import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { bookingService } from '@/services/bookingService'
import { ownerService } from '@/services/ownerService'
import type { BookingCheckout, BookingStatus, BookingCreate, BookingRead, MyBookingsParams, OwnerBookingsParams } from '@/types'

export function useMyBookings(params: MyBookingsParams) {
  return useQuery({
    queryKey: ['bookings', 'me', params],
    queryFn: () => bookingService.listMine(params),
    placeholderData: keepPreviousData,
  })
}

export interface UseBookingOptions {
  /** Poll interval in ms (or false), optionally computed from the current booking status. */
  refetchInterval?: number | false | ((status: BookingStatus | undefined) => number | false)
}

export function useBooking(id: number | undefined, options: UseBookingOptions = {}) {
  return useQuery({
    queryKey: ['booking', id],
    queryFn: () => bookingService.get(id ?? 0),
    enabled: id !== undefined && Number.isFinite(id),
    refetchInterval: (query) => {
      const ri = options.refetchInterval ?? false
      return typeof ri === 'function' ? ri(query.state.data?.status) : ri
    },
  })
}

export function useCreateBooking() {
  const qc = useQueryClient()
  return useMutation<BookingCheckout, unknown, BookingCreate>({
    mutationFn: (body) => bookingService.create(body),
    onSuccess: (data) => {
      qc.setQueryData(['booking', data.booking.id], data.booking)
      void qc.invalidateQueries({ queryKey: ['slots'] })
      void qc.invalidateQueries({ queryKey: ['bookings'] })
    },
  })
}

export interface CancelVars {
  id: number
  reason?: string
}

export function useCancelBooking() {
  const qc = useQueryClient()
  return useMutation<BookingRead, unknown, CancelVars>({
    mutationFn: ({ id, reason }) => bookingService.cancel(id, reason ? { reason } : {}),
    onSuccess: (data) => {
      qc.setQueryData(['booking', data.id], data)
      void qc.invalidateQueries({ queryKey: ['bookings'] })
      void qc.invalidateQueries({ queryKey: ['owner'] })
      void qc.invalidateQueries({ queryKey: ['slots'] })
    },
  })
}

export function useOwnerBookings(params: OwnerBookingsParams) {
  return useQuery({
    queryKey: ['owner', 'bookings', params],
    queryFn: () => ownerService.listBookings(params),
    placeholderData: keepPreviousData,
  })
}

export function useOwnerSummary() {
  return useQuery({ queryKey: ['owner', 'summary'], queryFn: () => ownerService.getSummary() })
}
