export type UserRole = 'player' | 'owner' | 'admin'

export interface UserRead {
  id: number
  email: string
  full_name: string
  phone: string | null
  role: UserRole
  is_active: boolean
  is_verified: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

/** password: min 8 chars, at least 1 letter + 1 digit. */
export interface RegisterRequest {
  email: string
  password: string
  full_name: string
  phone?: string
  role: 'player' | 'owner'
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface LogoutRequest {
  refresh_token: string
}

export interface UserUpdate {
  full_name?: string
  phone?: string | null
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

export interface VerifyEmailRequest {
  token: string
}

export interface MessageResponse {
  message?: string
  detail?: string
}
