import { motion } from 'framer-motion'
import { Inbox, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface EmptyStateProps {
  title: string
  description?: ReactNode
  icon?: LucideIcon
  /** Call-to-action (e.g. a GradientButton). */
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, icon: Icon = Inbox, action, className }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed bg-muted/30 px-6 py-12 text-center',
        className,
      )}
    >
      <div className="flex size-14 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="size-7" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </motion.div>
  )
}
