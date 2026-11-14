import {
  CalendarDays,
  LayoutDashboard,
  ListChecks,
  MapPinned,
  Search,
  ShieldCheck,
  Ticket,
  Users,
  type LucideIcon,
} from 'lucide-react'

import type { UserRole } from '@/types'

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  /** Match nested paths as active (NavLink `end` = !matchNested). */
  matchNested?: boolean
}

const playerItems: NavItem[] = [
  { label: 'Search', to: '/turfs', icon: Search },
  { label: 'My Bookings', to: '/my-bookings', icon: Ticket },
]

const ownerItems: NavItem[] = [
  { label: 'Dashboard', to: '/owner/dashboard', icon: LayoutDashboard },
  { label: 'Turfs', to: '/owner/turfs', icon: MapPinned },
  // Calendar lives at /owner/turfs/:id/calendar; the turfs page lets the owner pick a turf.
  { label: 'Calendar', to: '/owner/turfs?view=calendar', icon: CalendarDays },
  { label: 'Bookings', to: '/owner/bookings', icon: ListChecks },
]

const adminItems: NavItem[] = [
  { label: 'Admin', to: '/admin', icon: ShieldCheck },
  { label: 'Users', to: '/admin/users', icon: Users },
  { label: 'Turfs', to: '/admin/turfs', icon: MapPinned },
  { label: 'Bookings', to: '/admin/bookings', icon: ListChecks },
]

/** Navigation items by role (PRP Infrastructure): owners get everything players get. */
export function getNavItems(role: UserRole | null): NavItem[] {
  switch (role) {
    case 'owner':
      return [...ownerItems, ...playerItems]
    case 'admin':
      return adminItems
    case 'player':
      return playerItems
    default:
      return [{ label: 'Find a turf', to: '/turfs', icon: Search }]
  }
}
