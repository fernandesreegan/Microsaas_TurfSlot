import type {
  AuthConfig,
  ChangePasswordRequest,
  ForgotPasswordRequest,
  GoogleLoginRequest,
  LoginRequest,
  MessageResponse,
  RegisterRequest,
  ResetPasswordRequest,
  TokenPair,
  UserRead,
  UserUpdate,
  VerifyEmailRequest,
} from '@/types'

import { api } from './api'
import { tokenStorage } from './tokenStorage'

export const authService = {
  /** POST /auth/login -> TokenPair (tokens are persisted). */
  async login(body: LoginRequest): Promise<TokenPair> {
    const { data } = await api.post<TokenPair>('/auth/login', body)
    tokenStorage.setTokens(data)
    return data
  },

  /** POST /auth/google -> TokenPair (tokens are persisted). */
  async googleLogin(credential: string, role?: GoogleLoginRequest['role']): Promise<TokenPair> {
    const body: GoogleLoginRequest = role ? { credential, role } : { credential }
    const { data } = await api.post<TokenPair>('/auth/google', body)
    tokenStorage.setTokens(data)
    return data
  },

  /** GET /auth/config (public runtime auth configuration). */
  async getConfig(): Promise<AuthConfig> {
    const { data } = await api.get<AuthConfig>('/auth/config')
    return data
  },

  /** POST /auth/register -> 201 UserRead (does not log in). */
  async register(body: RegisterRequest): Promise<UserRead> {
    const { data } = await api.post<UserRead>('/auth/register', body)
    return data
  },

  /** GET /auth/me */
  async getMe(): Promise<UserRead> {
    const { data } = await api.get<UserRead>('/auth/me')
    return data
  },

  /** PUT /auth/me */
  async updateMe(body: UserUpdate): Promise<UserRead> {
    const { data } = await api.put<UserRead>('/auth/me', body)
    return data
  },

  /** POST /auth/refresh -> TokenPair (tokens are persisted). */
  async refresh(refreshToken: string): Promise<TokenPair> {
    const { data } = await api.post<TokenPair>('/auth/refresh', { refresh_token: refreshToken })
    tokenStorage.setTokens(data)
    return data
  },

  /** POST /auth/logout -> 204. Always clears local tokens. */
  async logout(): Promise<void> {
    const refreshToken = tokenStorage.getRefreshToken()
    try {
      if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken })
    } finally {
      tokenStorage.clear()
    }
  },

  /** POST /auth/change-password */
  async changePassword(body: ChangePasswordRequest): Promise<MessageResponse | null> {
    const { data } = await api.post<MessageResponse | null>('/auth/change-password', body)
    return data
  },

  /** POST /auth/forgot-password (always 200) */
  async forgotPassword(body: ForgotPasswordRequest): Promise<MessageResponse | null> {
    const { data } = await api.post<MessageResponse | null>('/auth/forgot-password', body)
    return data
  },

  /** POST /auth/reset-password */
  async resetPassword(body: ResetPasswordRequest): Promise<MessageResponse | null> {
    const { data } = await api.post<MessageResponse | null>('/auth/reset-password', body)
    return data
  },

  /** POST /auth/verify-email */
  async verifyEmail(body: VerifyEmailRequest): Promise<MessageResponse | null> {
    const { data } = await api.post<MessageResponse | null>('/auth/verify-email', body)
    return data
  },

  /** POST /auth/resend-verification */
  async resendVerification(): Promise<MessageResponse | null> {
    const { data } = await api.post<MessageResponse | null>('/auth/resend-verification')
    return data
  },
}
