import {
  BankOutlined,
  BarChartOutlined,
  EnvironmentOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Layout, Menu, Select, theme } from 'antd'
import { useTranslation } from 'react-i18next'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { LANGUAGE_STORAGE_KEY } from '../../shared/i18n'

/** Tenant-admin qatlami: sider-menyu (Xarita, Xodimlar, Obyektlar, Hisobotlar). */
export function AdminLayout() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  const menuItems = [
    { key: '/', icon: <EnvironmentOutlined />, label: t('menu.map') },
    { key: '/employees', icon: <TeamOutlined />, label: t('menu.employees') },
    { key: '/sites', icon: <BankOutlined />, label: t('menu.sites') },
    { key: '/reports', icon: <BarChartOutlined />, label: t('menu.reports') },
  ]

  const selectedKey =
    menuItems.find(
      (item) => item.key !== '/' && location.pathname.startsWith(item.key),
    )?.key ?? '/'

  const changeLanguage = (lng: string) => {
    void i18n.changeLanguage(lng)
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lng)
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg">
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 600,
          }}
        >
          {t('common.appName')}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: token.colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            paddingInline: 16,
          }}
        >
          <Select
            size="small"
            value={i18n.language}
            onChange={changeLanguage}
            options={[
              { value: 'uz', label: "O'zbekcha" },
              { value: 'ru', label: 'Русский' },
            ]}
            style={{ width: 120 }}
          />
        </Layout.Header>
        <Layout.Content
          style={{ margin: 16, display: 'flex', flexDirection: 'column' }}
        >
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
