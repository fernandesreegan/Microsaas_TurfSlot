import { toast } from 'sonner'

import { getApiError } from '@/services/api'

/** Show an API error as a toast; special-cases unverified email. */
export function toastApiError(err: unknown, title = 'Request failed'): void {
  const e = getApiError(err)
  if (e.code === 'EMAIL_NOT_VERIFIED') {
    toast.error('Please verify your email', {
      description: 'Check your inbox and click the verification link before continuing.',
    })
    return
  }
  toast.error(title, { description: e.detail })
}

/** Tailwind classes for native select/textarea elements to match shadcn inputs. */
export const nativeFieldClass =
  'w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30'
