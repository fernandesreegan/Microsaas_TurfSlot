import type { UserRole } from '@/types'

/** Default landing path for a role after login. */
export function homePathForRole(role: UserRole): string {
  switch (role) {
    case 'owner':
      return '/owner/dashboard'
    case 'admin':
      return '/admin'
    default:
      return '/turfs'
  }
}

/** Validates a `?next=` redirect target (same-origin relative paths only). */
export function safeNextPath(next: string | null | undefined): string | null {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : null
}
