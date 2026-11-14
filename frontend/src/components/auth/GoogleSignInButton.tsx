import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { useAuth } from '@/hooks/useAuth'
import { useGoogleIdentity } from '@/hooks/useGoogleIdentity'
import { homePathForRole, safeNextPath } from '@/lib/roles'
import { toastApiError } from '@/lib/toastError'
import { authService } from '@/services/authService'
import type { GoogleLoginRequest } from '@/types'
import type { GoogleCredentialResponse } from '@/types/google'

interface GoogleSignInButtonProps {
  /** Role for a newly created account (ignored for existing accounts). */
  role?: GoogleLoginRequest['role']
  /** Render an "or" divider above the button. */
  withDivider?: boolean
}

const MAX_BUTTON_WIDTH = 400

function useAuthConfig() {
  return useQuery({
    queryKey: ['auth', 'config'],
    queryFn: () => authService.getConfig(),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

/** Official Google button; renders nothing unless the backend has a Google client id. */
export function GoogleSignInButton({ role, withDivider = true }: GoogleSignInButtonProps) {
  const { data: config } = useAuthConfig()
  const clientId = config?.google_client_id ?? null
  const { gis } = useGoogleIdentity(clientId !== null)
  const containerRef = useRef<HTMLDivElement>(null)
  const roleRef = useRef(role)
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const nextRef = useRef(params.get('next'))

  useEffect(() => {
    roleRef.current = role
  }, [role])

  useEffect(() => {
    const container = containerRef.current
    if (!gis || !clientId || !container) return

    const onCredential = async (response: GoogleCredentialResponse): Promise<void> => {
      try {
        await authService.googleLogin(response.credential, roleRef.current)
        const me = await authService.getMe()
        setUser(me)
        toast.success(`Welcome, ${me.full_name}`)
        void navigate(safeNextPath(nextRef.current) ?? homePathForRole(me.role), { replace: true })
      } catch (err: unknown) {
        toastApiError(err, 'Google sign-in failed')
      }
    }

    gis.initialize({
      client_id: clientId,
      callback: (response) => void onCredential(response),
      ux_mode: 'popup',
      cancel_on_tap_outside: true,
    })
    container.replaceChildren()
    gis.renderButton(container, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'continue_with',
      shape: 'pill',
      logo_alignment: 'center',
      width: Math.min(MAX_BUTTON_WIDTH, Math.max(200, container.clientWidth || MAX_BUTTON_WIDTH)),
    })
  }, [gis, clientId, setUser, navigate])

  if (!clientId) return null

  return (
    <div className="space-y-4">
      {withDivider && (
        <div className="flex items-center gap-3 text-xs uppercase text-muted-foreground">
          <span className="h-px flex-1 bg-border" />
          or
          <span className="h-px flex-1 bg-border" />
        </div>
      )}
      <div ref={containerRef} className="flex min-h-10 w-full justify-center" />
    </div>
  )
}
