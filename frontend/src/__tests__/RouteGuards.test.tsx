import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { ProtectedRoute, RoleRoute } from '@/components/common/RouteGuards'
import { AuthContext, type AuthContextValue } from '@/context/AuthContext'
import type { UserRead, UserRole } from '@/types'

function makeUser(role: UserRole): UserRead {
  return {
    id: 1,
    email: 'u@example.com',
    full_name: 'Test User',
    phone: null,
    role,
    is_active: true,
    is_verified: true,
    created_at: '2026-01-01T00:00:00Z',
  }
}

function authValue(user: UserRead | null): AuthContextValue {
  return {
    user,
    isLoading: false,
    isAuthenticated: user !== null,
    login: async () => makeUser('player'),
    register: async () => makeUser('player'),
    logout: async () => undefined,
    refreshUser: async () => user,
    setUser: () => undefined,
    hasRole: (...roles) => (user ? roles.includes(user.role) : false),
  }
}

function renderAt(path: string, user: UserRead | null) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <p>home</p> },
      { path: '/login', element: <p>login</p> },
      { element: <ProtectedRoute />, children: [{ path: '/my-bookings', element: <p>my bookings</p> }] },
      { element: <RoleRoute roles={['owner']} />, children: [{ path: '/owner/dashboard', element: <p>owner</p> }] },
    ],
    { initialEntries: [path] },
  )
  render(
    <AuthContext.Provider value={authValue(user)}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
}

describe('route guards', () => {
  it('redirects guests to /login', async () => {
    renderAt('/my-bookings', null)
    expect(await screen.findByText('login')).toBeInTheDocument()
  })

  it('allows logged-in users through ProtectedRoute', async () => {
    renderAt('/my-bookings', makeUser('player'))
    expect(await screen.findByText('my bookings')).toBeInTheDocument()
  })

  it('blocks players from owner routes', async () => {
    renderAt('/owner/dashboard', makeUser('player'))
    expect(await screen.findByText('home')).toBeInTheDocument()
  })

  it('allows owners into owner routes', async () => {
    renderAt('/owner/dashboard', makeUser('owner'))
    expect(await screen.findByText('owner')).toBeInTheDocument()
  })
})
