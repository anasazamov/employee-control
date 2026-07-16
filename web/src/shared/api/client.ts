import axios from 'axios'

/** JWT saqlanadigan localStorage kaliti — login muvaffaqiyatida shu yerga yoziladi. */
export const ACCESS_TOKEN_KEY = 'access_token'

/** Backend API bazaviy URL (VITE_API_URL yoki default lokal). */
export const API_BASE_URL =
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/**
 * WS bazaviy URL — HTTP(S)'dan WS(S) hosil qilinadi.
 * http://host → ws://host, https://host → wss://host.
 */
export function getWsBaseUrl(): string {
  return API_BASE_URL.replace(/^http/i, 'ws')
}

/** FastAPI `{"detail": "..."}` xato-formatidan o'qiladigan xabar chiqaradi. */
export function getApiErrorMessage(error: unknown, fallback = 'Xatolik'): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)
      ?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      // Pydantic validatsiya-xatolari ro'yxati
      const first = detail[0] as { msg?: string } | string
      if (typeof first === 'string') return first
      if (first?.msg) return first.msg
    }
    if (error.message) return error.message
  }
  if (error instanceof Error) return error.message
  return fallback
}
