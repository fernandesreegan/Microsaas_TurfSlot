import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface PageWrapperProps {
  children: ReactNode
  className?: string
  /** Page title (also sets document.title). */
  title?: string
  /** Optional subtitle under the title. */
  description?: ReactNode
  /** Right-aligned header actions (buttons). */
  actions?: ReactNode
  /** Constrain width to the standard container (default true). */
  contained?: boolean
}

/** Every page is wrapped in this: page transition + optional header. */
export function PageWrapper({ children, className, title, description, actions, contained = true }: PageWrapperProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={cn(contained && 'container mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8', className)}
    >
      {title && <title>{`${title} · TurfSlot`}</title>}
      {(title || actions) && (
        <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1">
            {title && <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>}
            {description && <p className="text-muted-foreground">{description}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </motion.div>
  )
}
