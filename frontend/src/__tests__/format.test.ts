import { describe, expect, it } from 'vitest'

import { env } from '@/lib/env'
import { formatDistance, formatInTurfTz, formatMoney, humanize, todayInTz } from '@/lib/format'

describe('formatMoney', () => {
  it('converts minor units to major units', () => {
    expect(formatMoney(150000, 'INR', 'en-IN')).toBe('₹1,500.00')
    expect(formatMoney(1999, 'USD', 'en-US')).toBe('$19.99')
  })

  it('handles zero', () => {
    expect(formatMoney(0, 'USD', 'en-US')).toBe('$0.00')
  })
})

describe('formatInTurfTz', () => {
  it('formats a UTC instant in the turf timezone', () => {
    expect(formatInTurfTz('2026-11-14T10:30:00Z', 'Asia/Kolkata', 'HH:mm')).toBe('16:00')
    expect(formatInTurfTz('2026-07-01T10:00:00Z', 'Europe/London', 'HH:mm')).toBe('11:00')
    expect(formatInTurfTz('2026-12-01T10:00:00Z', 'Europe/London', 'HH:mm')).toBe('10:00')
  })

  it('computes the local date across midnight', () => {
    expect(todayInTz('Asia/Kolkata', new Date('2026-11-14T20:00:00Z'))).toBe('2026-11-15')
  })
})

describe('helpers', () => {
  it('humanizes enum values', () => {
    expect(humanize('refund_failed')).toBe('Refund Failed')
  })

  it('reads env with defaults', () => {
    expect(env.apiBaseUrl).toBe('http://localhost:8000/api/v1')
    expect(env.maxSlotsPerBooking).toBe(4)
  })
})

describe('formatDistance', () => {
  it('formats metres below 1 km and km above', () => {
    expect(formatDistance(0.004)).toBe('10 m')
    expect(formatDistance(0.853)).toBe('850 m')
    expect(formatDistance(2.43)).toBe('2.4 km')
    expect(formatDistance(12.6)).toBe('13 km')
  })
})
