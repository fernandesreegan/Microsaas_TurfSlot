import { AlertTriangle, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { getApiError } from '@/services/api'

export interface ErrorStateProps {
  title?: string
  /** Error object (any thrown value) — message is extracted via getApiError. */
  error?: unknown
  /** Explicit message (overrides error). */
  message?: ReactNode
  onRetry?: () => void
  className?: string
}

export function ErrorState({ title = 'Something went wrong', error, message, onRetry, className }: ErrorStateProps) {
  const text = message ?? (error !== undefined ? getApiError(error).detail : 'Please try again.')
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-6 py-10 text-center',
        className,
      )}
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="size-6" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="max-w-md text-sm text-muted-foreground">{text}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="mt-1">
          <RotateCw aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  )
}
