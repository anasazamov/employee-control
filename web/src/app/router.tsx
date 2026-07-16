import { createBrowserRouter } from 'react-router-dom'
import { LiveMap } from '../features/live-map'
import { AdminLayout } from './layouts/AdminLayout'
import { PlatformLayout } from './layouts/PlatformLayout'
import { LoginPage } from './pages/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    // Tenant-admin route-space
    path: '/',
    element: <AdminLayout />,
    children: [
      { index: true, element: <LiveMap /> },
      { path: 'employees', element: <PlaceholderPage titleKey="menu.employees" /> },
      { path: 'sites', element: <PlaceholderPage titleKey="menu.sites" /> },
      { path: 'reports', element: <PlaceholderPage titleKey="menu.reports" /> },
    ],
  },
  {
    // Platforma konsoli route-space (alohida auth-realm bo'ladi)
    path: '/platform',
    element: <PlatformLayout />,
    children: [
      { index: true, element: <PlaceholderPage titleKey="platform.tenants" /> },
    ],
  },
])
