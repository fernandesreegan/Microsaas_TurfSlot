import { lazy } from 'react'
import type { RouteObject } from 'react-router'

import { GuestOnlyRoute, ProtectedRoute, RoleRoute } from '@/components/common/RouteGuards'
import { AppLayout } from '@/components/layout/AppLayout'
import { RouteErrorBoundary } from '@/components/common/RouteErrorBoundary'

// Public
const HomePage = lazy(() => import('@/pages/public/HomePage'))
const TurfSearchPage = lazy(() => import('@/pages/public/TurfSearchPage'))
const TurfDetailPage = lazy(() => import('@/pages/public/TurfDetailPage'))
const NotFoundPage = lazy(() => import('@/pages/public/NotFoundPage'))

// Auth / account
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@/pages/auth/ResetPasswordPage'))
const VerifyEmailPage = lazy(() => import('@/pages/auth/VerifyEmailPage'))
const ProfilePage = lazy(() => import('@/pages/auth/ProfilePage'))
const SettingsPage = lazy(() => import('@/pages/auth/SettingsPage'))

// Player (any logged-in user)
const CheckoutPage = lazy(() => import('@/pages/player/CheckoutPage'))
const BookingDetailPage = lazy(() => import('@/pages/player/BookingDetailPage'))
const MyBookingsPage = lazy(() => import('@/pages/player/MyBookingsPage'))

// Owner
const OwnerDashboardPage = lazy(() => import('@/pages/owner/OwnerDashboardPage'))
const OwnerTurfsPage = lazy(() => import('@/pages/owner/OwnerTurfsPage'))
const TurfFormPage = lazy(() => import('@/pages/owner/TurfFormPage'))
const OwnerCalendarPage = lazy(() => import('@/pages/owner/OwnerCalendarPage'))
const OwnerBookingsPage = lazy(() => import('@/pages/owner/OwnerBookingsPage'))

// Admin
const AdminDashboardPage = lazy(() => import('@/pages/admin/AdminDashboardPage'))
const AdminUsersPage = lazy(() => import('@/pages/admin/AdminUsersPage'))
const AdminTurfsPage = lazy(() => import('@/pages/admin/AdminTurfsPage'))
const AdminBookingsPage = lazy(() => import('@/pages/admin/AdminBookingsPage'))

/** All 23 PRP routes + 404. */
export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    errorElement: <RouteErrorBoundary />,
    children: [
      // Public
      { path: '/', element: <HomePage /> },
      { path: '/turfs', element: <TurfSearchPage /> },
      { path: '/turfs/:slug', element: <TurfDetailPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
      { path: '/verify-email', element: <VerifyEmailPage /> },

      // Guests only
      {
        element: <GuestOnlyRoute />,
        children: [
          { path: '/login', element: <LoginPage /> },
          { path: '/register', element: <RegisterPage /> },
        ],
      },

      // Any logged-in user
      {
        element: <ProtectedRoute />,
        children: [
          { path: '/profile', element: <ProfilePage /> },
          { path: '/settings', element: <SettingsPage /> },
          { path: '/checkout/:bookingId', element: <CheckoutPage /> },
          { path: '/bookings/:id', element: <BookingDetailPage /> },
          { path: '/my-bookings', element: <MyBookingsPage /> },
        ],
      },

      // Owner
      {
        element: <RoleRoute roles={['owner']} />,
        children: [
          { path: '/owner/dashboard', element: <OwnerDashboardPage /> },
          { path: '/owner/turfs', element: <OwnerTurfsPage /> },
          { path: '/owner/turfs/new', element: <TurfFormPage /> },
          { path: '/owner/turfs/:id/edit', element: <TurfFormPage /> },
          { path: '/owner/turfs/:id/calendar', element: <OwnerCalendarPage /> },
          { path: '/owner/bookings', element: <OwnerBookingsPage /> },
        ],
      },

      // Admin
      {
        element: <RoleRoute roles={['admin']} />,
        children: [
          { path: '/admin', element: <AdminDashboardPage /> },
          { path: '/admin/users', element: <AdminUsersPage /> },
          { path: '/admin/turfs', element: <AdminTurfsPage /> },
          { path: '/admin/bookings', element: <AdminBookingsPage /> },
        ],
      },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
