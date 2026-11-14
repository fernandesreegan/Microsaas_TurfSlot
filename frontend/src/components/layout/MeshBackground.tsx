import { motion } from 'framer-motion'

import { cn } from '@/lib/utils'

export interface MeshBackgroundProps {
  className?: string
}

/** Animated turf-green mesh gradient backdrop for landing and auth pages. */
export function MeshBackground({ className }: MeshBackgroundProps) {
  return (
    <div aria-hidden="true" className={cn('pointer-events-none fixed inset-0 -z-10 overflow-hidden', className)}>
      <div className="absolute inset-0 bg-linear-to-br from-secondary via-background to-accent/40" />
      {/* subtle pitch lines */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-size-[64px_64px] opacity-30 mask-[radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />
      <motion.div
        className="absolute -top-24 left-1/4 size-96 rounded-full bg-brand-from/30 blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, 30, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute right-1/4 -bottom-24 size-96 rounded-full bg-brand-to/30 blur-3xl"
        animate={{ x: [0, -40, 0], y: [0, -30, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute top-1/3 -right-20 size-72 rounded-full bg-brand-via/20 blur-3xl"
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  )
}
