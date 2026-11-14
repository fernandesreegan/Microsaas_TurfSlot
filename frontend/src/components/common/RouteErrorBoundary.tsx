import { isRouteErrorResponse, useNavigate, useRouteError } from 'react-router'

import { ErrorState } from '@/components/common/ErrorState'

/** Router-level error element (render errors, failed lazy chunk loads). */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'An unexpected error occurred.'

  return (
    <div className="container mx-auto flex min-h-svh max-w-xl items-center px-4">
      <ErrorState
        className="w-full"
        title="Something went wrong"
        message={message}
        onRetry={() => navigate(0)}
      />
    </div>
  )
}
