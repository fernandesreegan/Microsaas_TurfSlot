/** Minimal typings for Google Identity Services (https://accounts.google.com/gsi/client). */

export interface GoogleCredentialResponse {
  /** The Google ID token (JWT). */
  credential: string
  select_by?: string
}

export interface GoogleIdConfiguration {
  client_id: string
  callback: (response: GoogleCredentialResponse) => void
  auto_select?: boolean
  cancel_on_tap_outside?: boolean
  context?: 'signin' | 'signup' | 'use'
  ux_mode?: 'popup' | 'redirect'
  itp_support?: boolean
}

export interface GoogleButtonConfiguration {
  type?: 'standard' | 'icon'
  theme?: 'outline' | 'filled_blue' | 'filled_black'
  size?: 'large' | 'medium' | 'small'
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
  shape?: 'rectangular' | 'pill' | 'circle' | 'square'
  logo_alignment?: 'left' | 'center'
  width?: number
  locale?: string
}

export interface GoogleAccountsId {
  initialize: (config: GoogleIdConfiguration) => void
  renderButton: (parent: HTMLElement, options: GoogleButtonConfiguration) => void
  prompt: () => void
  disableAutoSelect: () => void
  cancel: () => void
}

export interface GoogleIdentityServices {
  accounts: { id: GoogleAccountsId }
}

declare global {
  interface Window {
    google?: GoogleIdentityServices
  }
}
