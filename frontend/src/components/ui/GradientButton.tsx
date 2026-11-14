import { motion } from 'framer-motion'
import { Loader2 } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MotionButton = motion.create(Button)

type ButtonProps = ComponentProps<typeof Button>

type ConflictingHandlers =
  | 'onDrag'
  | 'onDragStart'
  | 'onDragEnd'
  | 'onAnimationStart'
  | 'onAnimationEnd'
  | 'onAnimationIteration'

export interface GradientButtonProps extends Omit<ButtonProps, ConflictingHandlers | 'variant'> {
  /** Shows a spinner and disables the button. */
  loading?: boolean
  /** Optional label while loading (defaults to children). */
  loadingText?: ReactNode
  /** `gradient` (brand turf gradient, default) or `outline` (bordered, gradient-tinted text). */
  tone?: 'gradient' | 'outline'
  fullWidth?: boolean
}

/** Primary call-to-action button: shadcn Button + turf gradient + hover/tap motion + loading state. */
export function GradientButton({
  children,
  className,
  loading = false,
  loadingText,
  disabled,
  tone = 'gradient',
  fullWidth = false,
  size = 'lg',
  type = 'button',
  ...props
}: GradientButtonProps) {
  const isDisabled = disabled || loading
  return (
    <MotionButton
      type={type}
      size={size}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      whileHover={isDisabled ? undefined : { scale: 1.02, y: -2 }}
      whileTap={isDisabled ? undefined : { scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
      className={cn(
        'rounded-full font-semibold',
        tone === 'gradient' &&
          'bg-linear-to-r from-brand-from via-brand-via to-brand-to text-primary-foreground shadow-md shadow-primary/25 hover:shadow-lg hover:shadow-primary/30',
        tone === 'outline' &&
          'border-2 border-primary bg-transparent text-primary hover:bg-primary/10',
        fullWidth && 'w-full',
        className,
      )}
      {...props}
    >
      {loading && <Loader2 className="animate-spin" aria-hidden="true" />}
      {loading && loadingText ? loadingText : children}
    </MotionButton>
  )
}
