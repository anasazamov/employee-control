import { create } from 'zustand'
import { ACCESS_TOKEN_KEY } from '../api/client'
import type { Role } from '../api/types'
import { decodeJwt } from './jwt'

const REFRESH_TOKEN_KEY = 'refresh_token'
const AUTH_USER_KEY = 'auth_user'

export interface AuthUser {
  id: string
  role: Role
  org_id: string
  org_name?: string
  full_name?: string
}

export interface SetSessionInput {
  accessToken: string
  refreshToken?: string
  user?: Partial<AuthUser>
}

interface AuthState {
  accessToken: string | null
  user: AuthUser | null
  /** Login (paste-token yoki OTP-activate) muvaffaqiyatida sessiyani o'rnatadi. */
  setSession: (input: SetSessionInput) => void
  /** Store'dagi user maydonlarini yangilaydi (masalan /me'dan full_name). */
  patchUser: (patch: Partial<AuthUser>) => void
  /** Sessiyani tozalaydi (localStorage ham). */
  logout: () => void
}

function loadUser(): AuthUser | null {
  const raw = localStorage.getItem(AUTH_USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

function persistUser(user: AuthUser | null): void {
  if (user) localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(AUTH_USER_KEY)
}

export const useAuthStore = create<AuthState>((set, get) => ({
  // Axios interceptor to'g'ridan-to'g'ri localStorage['access_token']'ni o'qiydi —
  // shu sabab boshlang'ich holat ham shu kalitdan tiklanadi.
  accessToken: localStorage.getItem(ACCESS_TOKEN_KEY),
  user: loadUser(),

  setSession: ({ accessToken, refreshToken, user }) => {
    const claims = decodeJwt(accessToken) ?? {}
    const merged: AuthUser = {
      id: user?.id ?? claims.sub ?? '',
      role: (user?.role ?? (claims.role as Role | undefined)) ?? 'field_employee',
      org_id: user?.org_id ?? claims.org_id ?? '',
      org_name: user?.org_name ?? claims.org_name,
      full_name: user?.full_name,
    }
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
    if (refreshToken) localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
    persistUser(merged)
    set({ accessToken, user: merged })
  },

  patchUser: (patch) => {
    const current = get().user
    if (!current) return
    const next = { ...current, ...patch }
    persistUser(next)
    set({ user: next })
  },

  logout: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(AUTH_USER_KEY)
    set({ accessToken: null, user: null })
  },
}))
