import { motion, type Variants } from 'framer-motion'
import { Children, isValidElement, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

const containerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3, ease: 'easeOut' } },
}

export interface AnimatedListProps {
  children: ReactNode
  /** Classes for the container (e.g. `grid gap-4 md:grid-cols-3`). */
  className?: string
  itemClassName?: string
  /** Render as `ul` with `li` items for semantic lists. */
  as?: 'div' | 'ul'
}

/** Staggered fade-in list. Children with `key`s keep their keys. */
export function AnimatedList({ children, className, itemClassName, as = 'div' }: AnimatedListProps) {
  const Container = as === 'ul' ? motion.ul : motion.div
  const Item = as === 'ul' ? motion.li : motion.div
  return (
    <Container initial="hidden" animate="visible" variants={containerVariants} className={className}>
      {Children.toArray(children).map((child, i) => (
        <Item
          key={isValidElement(child) && child.key !== null ? child.key : i}
          variants={itemVariants}
          className={cn(itemClassName)}
        >
          {child}
        </Item>
      ))}
    </Container>
  )
}
