import { useEffect, useState } from 'react'

import type { GoogleAccountsId } from '@/types/google'

const GSI_SRC = 'https://accounts.google.com/gsi/client'

let loadPromise: Promise<GoogleAccountsId> | null = null

/** Load the Google Identity Services script once and resolve with `google.accounts.id`. */
export function loadGoogleIdentity(): Promise<GoogleAccountsId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id)
  if (loadPromise) return loadPromise
  loadPromise = new Promise<GoogleAccountsId>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GSI_SRC
    script.async = true
    script.defer = true
    script.onload = () => {
      const gis = window.google?.accounts?.id
      if (gis) resolve(gis)
      else reject(new Error('Google Identity Services failed to initialise'))
    }
    script.onerror = () => {
      loadPromise = null
      script.remove()
      reject(new Error('Could not load Google Identity Services'))
    }
    document.head.appendChild(script)
  })
  return loadPromise
}

export interface GoogleIdentityState {
  gis: GoogleAccountsId | null
  error: Error | null
}

/** Load GIS when `enabled`; returns the `google.accounts.id` API once available. */
export function useGoogleIdentity(enabled: boolean): GoogleIdentityState {
  const [state, setState] = useState<GoogleIdentityState>({ gis: null, error: null })

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    loadGoogleIdentity()
      .then((gis) => {
        if (!cancelled) setState({ gis, error: null })
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ gis: null, error: error instanceof Error ? error : new Error(String(error)) })
      })
    return () => {
      cancelled = true
    }
  }, [enabled])

  return state
}
