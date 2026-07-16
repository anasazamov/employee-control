import { createBrowserRouter } from 'react-router-dom'
import { LiveMap } from '../features/live-map'
import { EmployeesPage } from '../features/employees'
import { SitesPage } from '../features/sites'
import { ReviewQueuePage } from '../features/review'
import { HistoryPage } from '../features/history'
import { AdminLayout } from './layouts/AdminLayout'
import { PlatformLayout } from './layouts/PlatformLayout'
import { RequireAuth } from './guards/RequireAuth'
import { LoginPage } from './pages/LoginPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    // Autentifikatsiya talab qilinadigan tenant-admin route-space
    element: <RequireAuth />,
    children: [
      {
        path: '/',
        element: <AdminLayout />,
        children: [
          { index: true, element: <LiveMap /> },
          { path: 'employees', element: <EmployeesPage /> },
          { path: 'sites', element: <SitesPage /> },
          { path: 'review', element: <ReviewQueuePage /> },
          { path: 'history', element: <HistoryPage /> },
        ],
      },
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
