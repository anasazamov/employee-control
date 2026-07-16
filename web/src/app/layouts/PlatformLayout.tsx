import { Layout } from 'antd'
import { useTranslation } from 'react-i18next'
import { Outlet } from 'react-router-dom'

// Platforma konsoli — alohida route-space; keyinchalik alohida auth-realm va
// o'z MFA'si bo'ladi (docs/PLAN.md §10, "Platforma konsoli").
export function PlatformLayout() {
  const { t } = useTranslation()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header
        style={{
          display: 'flex',
          alignItems: 'center',
          color: '#fff',
          fontSize: 18,
          fontWeight: 600,
        }}
      >
        {t('common.platformConsole')}
      </Layout.Header>
      <Layout.Content style={{ margin: 16 }}>
        <Outlet />
      </Layout.Content>
    </Layout>
  )
}
