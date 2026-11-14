import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ownerService } from '@/services/ownerService'
import { turfService } from '@/services/turfService'
import type { TurfCreate, TurfRead, TurfSearchParams } from '@/types'

export function useTurfs(params: TurfSearchParams) {
  return useQuery({
    queryKey: ['turfs', params],
    queryFn: () => turfService.search(params),
    placeholderData: keepPreviousData,
  })
}

export function useTurf(slugOrId: string | number | undefined) {
  return useQuery({
    queryKey: ['turf', slugOrId],
    queryFn: () => turfService.get(slugOrId ?? ''),
    enabled: slugOrId !== undefined && slugOrId !== '',
  })
}

export function useSlots(turfId: number | undefined, date: string) {
  return useQuery({
    queryKey: ['slots', turfId, date],
    queryFn: () => turfService.getSlots(turfId ?? 0, date),
    enabled: turfId !== undefined && date !== '',
    staleTime: 10_000,
  })
}

export function useOwnerTurfs() {
  return useQuery({ queryKey: ['owner', 'turfs'], queryFn: () => ownerService.listTurfs() })
}

export interface SaveTurfVars {
  id?: number
  body: TurfCreate
}

export function useSaveTurf() {
  const qc = useQueryClient()
  return useMutation<TurfRead, unknown, SaveTurfVars>({
    mutationFn: ({ id, body }) => (id ? turfService.update(id, body) : turfService.create(body)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['owner', 'turfs'] })
      void qc.invalidateQueries({ queryKey: ['turfs'] })
      void qc.invalidateQueries({ queryKey: ['turf'] })
    },
  })
}
