import { Suspense } from 'react'
import { Outlet, ScrollRestoration } from 'react-router'

import { FullPageSpinner } from '@/components/common/LoadingSpinner'

import { Footer } from './Footer'
import { Navbar } from './Navbar'

/** Root layout: sticky navbar, page outlet (lazy pages suspend here), footer. */
export function AppLayout() {
  return (
    <div className="flex min-h-svh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main" className="flex flex-1 flex-col">
        <Suspense fallback={<FullPageSpinner />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      <ScrollRestoration />
    </div>
  )
}
