import type { TokenPair } from '@/types'

const ACCESS_KEY = 'turfslot_access_token'
const REFRESH_KEY = 'turfslot_refresh_token'

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // storage unavailable (private mode etc.)
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key)
  } catch {
    // ignore
  }
}

export const tokenStorage = {
  getAccessToken(): string | null {
    return safeGet(ACCESS_KEY)
  },
  getRefreshToken(): string | null {
    return safeGet(REFRESH_KEY)
  },
  setTokens(tokens: Pick<TokenPair, 'access_token' | 'refresh_token'>): void {
    safeSet(ACCESS_KEY, tokens.access_token)
    safeSet(REFRESH_KEY, tokens.refresh_token)
  },
  clear(): void {
    safeRemove(ACCESS_KEY)
    safeRemove(REFRESH_KEY)
  },
  hasTokens(): boolean {
    return safeGet(ACCESS_KEY) !== null || safeGet(REFRESH_KEY) !== null
  },
}
