import type { DaySlots, Page, TurfCreate, TurfDetail, TurfRead, TurfSearchItem, TurfSearchParams, TurfUpdate } from '@/types'

import { api } from './api'

export const turfService = {
  /** GET /turfs */
  async search(params: TurfSearchParams): Promise<Page<TurfSearchItem>> {
    const { data } = await api.get<Page<TurfSearchItem>>('/turfs', { params })
    return data
  },

  /** GET /turfs/{id_or_slug} */
  async get(slugOrId: string | number): Promise<TurfDetail> {
    const { data } = await api.get<TurfDetail>(`/turfs/${slugOrId}`)
    return data
  },

  /** GET /turfs/{id}/slots?date=YYYY-MM-DD */
  async getSlots(turfId: number, date: string): Promise<DaySlots> {
    const { data } = await api.get<DaySlots>(`/turfs/${turfId}/slots`, { params: { date } })
    return data
  },

  /** POST /turfs */
  async create(body: TurfCreate): Promise<TurfRead> {
    const { data } = await api.post<TurfRead>('/turfs', body)
    return data
  },

  /** PUT /turfs/{id} */
  async update(id: number, body: TurfUpdate): Promise<TurfRead> {
    const { data } = await api.put<TurfRead>(`/turfs/${id}`, body)
    return data
  },
}
