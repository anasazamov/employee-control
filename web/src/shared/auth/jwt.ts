// JWT payload'ini brauzerda base64url-dekodlash. Imzo TEKSHIRILMAYDI —
// faqat UI uchun claim'lar (org_id, sub, role) o'qiladi; ishonch server tomonda.

export interface JwtClaims {
  sub?: string
  org_id?: string
  org_name?: string
  role?: string
  device_id?: string
  exp?: number
  [key: string]: unknown
}

export function decodeJwt(token: string): JwtClaims | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join(''),
    )
    return JSON.parse(json) as JwtClaims
  } catch {
    return null
  }
}
