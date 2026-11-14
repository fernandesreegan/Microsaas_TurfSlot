import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { AUTH_LOGOUT_EVENT } from '@/services/api'
import { authService } from '@/services/authService'
import { tokenStorage } from '@/services/tokenStorage'
import type { RegisterRequest, UserRead, UserRole } from '@/types'

export interface AuthContextValue {
  user: UserRead | null
  isLoading: boolean
  isAuthenticated: boolean
  /** Logs in, persists tokens, loads /auth/me. Throws on failure (use getApiError). */
  login: (email: string, password: string) => Promise<UserRead>
  /** Registers (does NOT log in; backend sends verification email). Throws on failure. */
  register: (data: RegisterRequest) => Promise<UserRead>
  /** Revokes the refresh token server-side (best effort) and clears local state. */
  logout: () => Promise<void>
  /** Re-fetches /auth/me (e.g. after verifying email or updating profile). */
  refreshUser: () => Promise<UserRead | null>
  /** Replace the cached user (e.g. with the PUT /auth/me response). */
  setUser: (user: UserRead | null) => void
  hasRole: (...roles: UserRole[]) => boolean
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<UserRead | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(() => tokenStorage.hasTokens())

  const refreshUser = useCallback(async (): Promise<UserRead | null> => {
    if (!tokenStorage.hasTokens()) {
      setUser(null)
      return null
    }
    try {
      const me = await authService.getMe()
      setUser(me)
      return me
    } catch {
      tokenStorage.clear()
      setUser(null)
      return null
    }
  }, [])

  // Bootstrap session on mount.
  useEffect(() => {
    if (!tokenStorage.hasTokens()) return
    let cancelled = false
    authService
      .getMe()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch(() => {
        if (!cancelled) {
          tokenStorage.clear()
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Session lost in the API layer (refresh failed).
  useEffect(() => {
    const onLogout = () => {
      setUser(null)
      queryClient.clear()
    }
    window.addEventListener(AUTH_LOGOUT_EVENT, onLogout)
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, onLogout)
  }, [queryClient])

  const login = useCallback(async (email: string, password: string): Promise<UserRead> => {
    await authService.login({ email: email.trim().toLowerCase(), password })
    const me = await authService.getMe()
    setUser(me)
    return me
  }, [])

  const register = useCallback(async (data: RegisterRequest): Promise<UserRead> => {
    return authService.register({ ...data, email: data.email.trim().toLowerCase() })
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authService.logout()
    } catch {
      // ignore network errors; local tokens are cleared regardless
    } finally {
      setUser(null)
      queryClient.clear()
    }
  }, [queryClient])

  const hasRole = useCallback((...roles: UserRole[]) => (user ? roles.includes(user.role) : false), [user])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      register,
      logout,
      refreshUser,
      setUser,
      hasRole,
    }),
    [user, isLoading, login, register, logout, refreshUser, hasRole],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
