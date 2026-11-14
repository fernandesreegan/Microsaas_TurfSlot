import { Link } from 'react-router'

import { Logo } from './Logo'

export function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer className="mt-auto border-t border-border/60 bg-background/60 backdrop-blur">
      <div className="container mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 md:flex-row md:items-center md:justify-between lg:px-8">
        <div className="space-y-2">
          <Logo />
          <p className="max-w-sm text-sm text-muted-foreground">
            Find a turf, see live availability and book in under a minute.
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <Link to="/turfs" className="hover:text-foreground">
            Find a turf
          </Link>
          <Link to="/register" className="hover:text-foreground">
            List your turf
          </Link>
          <Link to="/my-bookings" className="hover:text-foreground">
            My bookings
          </Link>
        </nav>
        <p className="text-xs text-muted-foreground">&copy; {year} TurfSlot. Free cancellation up to 24h before.</p>
      </div>
    </footer>
  )
}
