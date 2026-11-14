import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router'

import { FullPageSpinner } from '@/components/common/LoadingSpinner'
import { useAuth } from '@/hooks/useAuth'
import { homePathForRole, safeNextPath } from '@/lib/roles'
import type { UserRole } from '@/types'

interface GuardProps {
  /** If omitted, renders <Outlet /> (for use as a layout route). */
  children?: ReactNode
}

/** Requires a logged-in user; otherwise redirects to /login?next=<current path>. */
export function ProtectedRoute({ children }: GuardProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageSpinner label="Checking your session" />
  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children ? <>{children}</> : <Outlet />
}

export interface RoleRouteProps extends GuardProps {
  roles: UserRole[]
  /** Where to send logged-in users without the role (default "/"). */
  redirectTo?: string
}

/** Requires a logged-in user whose role is in `roles`. */
export function RoleRoute({ roles, redirectTo = '/', children }: RoleRouteProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullPageSpinner label="Checking your session" />
  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  if (!roles.includes(user.role)) return <Navigate to={redirectTo} replace />
  return children ? <>{children}</> : <Outlet />
}

/** Only for guests (login/register). Logged-in users go to `?next=` or their role home. */
export function GuestOnlyRoute({ children }: GuardProps) {
  const { user, isLoading } = useAuth()
  const [params] = useSearchParams()

  if (isLoading) return <FullPageSpinner />
  if (user) {
    return <Navigate to={safeNextPath(params.get('next')) ?? homePathForRole(user.role)} replace />
  }
  return children ? <>{children}</> : <Outlet />
}
