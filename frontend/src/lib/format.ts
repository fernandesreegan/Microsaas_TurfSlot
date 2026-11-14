import { tz } from '@date-fns/tz'
import { format, parseISO } from 'date-fns'

/**
 * Format an amount in minor units (e.g. paise/cents) as localized currency.
 * `formatMoney(150000, 'INR')` -> "₹1,500.00"
 */
export function formatMoney(minor: number, currency: string, locale?: string): string {
  const code = (currency || 'INR').toUpperCase()
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: code,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(minor / 100)
  } catch {
    return `${(minor / 100).toFixed(2)} ${code}`
  }
}

/**
 * Format an ISO 8601 UTC timestamp in the turf's IANA timezone using a date-fns pattern.
 * `formatInTurfTz('2026-11-14T10:30:00Z', 'Asia/Kolkata', 'HH:mm')` -> "16:00"
 */
export function formatInTurfTz(iso: string, timeZone: string, pattern: string): string {
  return format(parseISO(iso), pattern, { in: tz(timeZone) })
}

/** Today's date (YYYY-MM-DD) in the given IANA timezone — use for `date` query params. */
export function todayInTz(timeZone: string, now: Date = new Date()): string {
  return format(now, 'yyyy-MM-dd', { in: tz(timeZone) })
}

/** "HH:MM:SS" or "HH:MM" -> "HH:MM" */
export function formatTimeHHMM(time: string): string {
  return time.slice(0, 5)
}

/** Capitalize a snake/lowercase enum value for display: "pickleball" -> "Pickleball". */
export function humanize(value: string): string {
  return value
    .split('_')
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(' ')
}
