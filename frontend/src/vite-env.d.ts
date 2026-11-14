/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend origin, e.g. http://localhost:8000 (the client appends /api/v1). */
  readonly VITE_API_URL: string
  /** Max consecutive slots per booking (mirrors backend MAX_SLOTS_PER_BOOKING). */
  readonly VITE_MAX_SLOTS_PER_BOOKING?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
