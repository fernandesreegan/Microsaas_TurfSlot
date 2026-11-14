import { motion } from 'framer-motion'
import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'

import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type ConflictingHandlers =
  | 'onDrag'
  | 'onDragStart'
  | 'onDragEnd'
  | 'onAnimationStart'
  | 'onAnimationEnd'
  | 'onAnimationIteration'

export interface AnimatedInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, ConflictingHandlers> {
  label?: string
  error?: string
  hint?: string
  /** Icon rendered inside the input on the left. */
  leftIcon?: ReactNode
  /** Element rendered inside the input on the right (e.g. show-password toggle). */
  rightElement?: ReactNode
  containerClassName?: string
}

/**
 * Labeled input with focus animation and error display.
 * Works with react-hook-form: `<AnimatedInput {...register('email')} error={errors.email?.message} />`.
 */
export const AnimatedInput = forwardRef<HTMLInputElement, AnimatedInputProps>(function AnimatedInput(
  { label, error, hint, leftIcon, rightElement, className, containerClassName, id, ...props },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const errorId = `${inputId}-error`
  const hintId = `${inputId}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('space-y-1.5', containerClassName)}>
      {label && (
        <Label htmlFor={inputId} className={cn(error && 'text-destructive')}>
          {label}
        </Label>
      )}
      <div className="relative">
        {leftIcon && (
          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted-foreground [&_svg]:size-4">
            {leftIcon}
          </span>
        )}
        <motion.input
          ref={ref}
          id={inputId}
          whileFocus={{ scale: 1.01 }}
          transition={{ type: 'spring', stiffness: 400, damping: 25 }}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            'flex h-11 w-full rounded-xl border-2 border-input bg-background/70 px-4 py-2 text-base shadow-xs outline-none transition-colors md:text-sm',
            'placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-ring/30',
            'disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-destructive focus-visible:border-destructive focus-visible:ring-destructive/20',
            leftIcon && 'pl-10',
            rightElement && 'pr-11',
            className,
          )}
          {...props}
        />
        {rightElement && <span className="absolute inset-y-0 right-2 flex items-center">{rightElement}</span>}
      </div>
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <motion.p
          id={errorId}
          role="alert"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm text-destructive"
        >
          {error}
        </motion.p>
      )}
    </div>
  )
})
