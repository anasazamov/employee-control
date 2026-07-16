import axios from 'axios'

/** JWT saqlanadigan localStorage kaliti — login muvaffaqiyatida shu yerga yoziladi. */
export const ACCESS_TOKEN_KEY = 'access_token'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
