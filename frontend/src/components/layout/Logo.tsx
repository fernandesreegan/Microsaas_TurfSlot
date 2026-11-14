import { cn } from '@/lib/utils'

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2 text-lg font-extrabold tracking-tight', className)}>
      <span className="flex size-8 items-center justify-center rounded-xl bg-linear-to-br from-brand-from to-brand-to text-sm font-black text-primary-foreground shadow-md shadow-primary/30">
        TS
      </span>
      <span>
        Turf<span className="text-primary">Slot</span>
      </span>
    </span>
  )
}
