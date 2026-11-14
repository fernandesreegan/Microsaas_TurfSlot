import { motion, type HTMLMotionProps } from 'framer-motion'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface GlassCardProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  children?: ReactNode
  /** Lift + scale on hover (default true). Disable for large static containers like forms. */
  hoverable?: boolean
  /** Remove default padding. */
  noPadding?: boolean
}

/** Frosted-glass card with fade-in and hover elevation. */
export function GlassCard({ children, className, hoverable = true, noPadding = false, ...props }: GlassCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      whileHover={hoverable ? { y: -4, scale: 1.01 } : undefined}
      className={cn(
        'rounded-2xl border border-white/40 bg-card/70 text-card-foreground shadow-lg shadow-primary/5 backdrop-blur-xl transition-shadow',
        'dark:border-white/10 dark:bg-card/60',
        hoverable && 'hover:shadow-xl hover:shadow-primary/10',
        !noPadding && 'p-6',
        className,
      )}
      {...props}
    >
      {children}
    </motion.div>
  )
}
