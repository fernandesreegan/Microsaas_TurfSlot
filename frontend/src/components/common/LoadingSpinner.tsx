import { Loader2 } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface LoadingSpinnerProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

const sizeClass = { sm: 'size-4', md: 'size-6', lg: 'size-10' } as const

export function LoadingSpinner({ className, size = 'md', label = 'Loading' }: LoadingSpinnerProps) {
  return (
    <div role="status" aria-live="polite" className={cn('flex items-center justify-center', className)}>
      <Loader2 className={cn('animate-spin text-primary', sizeClass[size])} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  )
}

/** Full-area centered spinner (route-level Suspense fallback / auth bootstrap). */
export function FullPageSpinner({ label }: { label?: string }) {
  return <LoadingSpinner size="lg" label={label} className="min-h-[50vh]" />
}

export interface PageSkeletonProps {
  /** Number of content rows/cards. */
  rows?: number
  variant?: 'list' | 'grid'
  className?: string
}

/** Generic page-shaped skeleton: header + list or card grid. */
export function PageSkeleton({ rows = 6, variant = 'list', className }: PageSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Loading content"
      className={cn('container mx-auto w-full max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8', className)}
    >
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      {variant === 'grid' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: rows }, (_, i) => (
            <Skeleton key={i} className="h-56 rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {Array.from({ length: rows }, (_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      )}
    </div>
  )
}
