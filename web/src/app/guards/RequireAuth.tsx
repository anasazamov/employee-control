import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../shared/auth/store'

/** Autentifikatsiyasiz foydalanuvchini /login'ga yo'naltiruvchi route-guard. */
export function RequireAuth() {
  const accessToken = useAuthStore((s) => s.accessToken)
  const location = useLocation()

  if (!accessToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
