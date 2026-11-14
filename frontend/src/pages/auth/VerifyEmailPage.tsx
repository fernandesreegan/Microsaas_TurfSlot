import { useMutation } from '@tanstack/react-query'
import { CheckCircle2, XCircle } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router'

import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { PageWrapper } from '@/components/layout/PageWrapper'
import { GlassCard } from '@/components/ui/GlassCard'
import { useAuth } from '@/hooks/useAuth'
import { getApiError } from '@/services/api'
import { authService } from '@/services/authService'

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const { isAuthenticated, refreshUser } = useAuth()
  const submitted = useRef(false)
  const verify = useMutation({
    mutationFn: (t: string) => authService.verifyEmail({ token: t }),
    onSuccess: () => {
      if (isAuthenticated) void refreshUser()
    },
  })

  useEffect(() => {
    if (token && !submitted.current) {
      submitted.current = true
      verify.mutate(token)
    }
  }, [token, verify])

  return (
    <PageWrapper title="Verify email" className="max-w-md">
      <GlassCard hoverable={false} className="flex flex-col items-center gap-4 text-center">
        {!token ? (
          <p className="text-muted-foreground">Missing verification token. Use the link from your email.</p>
        ) : verify.isError ? (
          <>
            <XCircle className="size-12 text-destructive" aria-hidden="true" />
            <p>{getApiError(verify.error).detail}</p>
          </>
        ) : verify.isSuccess ? (
          <>
            <CheckCircle2 className="size-12 text-primary" aria-hidden="true" />
            <p>Your email is verified. You can now book turfs.</p>
            <Link to={isAuthenticated ? '/turfs' : '/login'} className="font-medium text-primary hover:underline">
              {isAuthenticated ? 'Find a turf' : 'Log in'}
            </Link>
          </>
        ) : (
          <LoadingSpinner label="Verifying" />
        )}
      </GlassCard>
    </PageWrapper>
  )
}
