import { QueryClient } from '@tanstack/react-query'
import { AxiosError } from 'axios'

/** Don't retry client errors (4xx); retry other failures up to 2 times. */
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof AxiosError) {
    const status = error.response?.status
    if (status !== undefined && status >= 400 && status < 500) return false
  }
  return failureCount < 2
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: shouldRetry,
      },
      mutations: {
        retry: false,
      },
    },
  })
}

export const queryClient = createQueryClient()
