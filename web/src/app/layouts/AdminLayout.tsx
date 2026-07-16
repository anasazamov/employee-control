import {
  BankOutlined,
  EnvironmentOutlined,
  HistoryOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Button, Layout, Menu, Select, Space, Tag, Typography, theme } from 'antd'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { LANGUAGE_STORAGE_KEY } from '../../shared/i18n'
import { useAuthStore } from '../../shared/auth/store'
import { canReview } from '../../shared/auth/roles'

/** Tenant-admin qatlami: sider-menyu + org/rol/chiqish sarlavhada. */
export function AdminLayout() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)

  const menuItems = useMemo(() => {
    const items = [
      { key: '/', icon: <EnvironmentOutlined />, label: t('menu.map') },
      { key: '/employees', icon: <TeamOutlined />, label: t('menu.employees') },
      { key: '/sites', icon: <BankOutlined />, label: t('menu.sites') },
    ]
    if (canReview(user?.role)) {
      items.push({
        key: '/review',
        icon: <SafetyCertificateOutlined />,
        label: t('menu.review'),
      })
    }
    items.push({
      key: '/history',
      icon: <HistoryOutlined />,
      label: t('menu.history'),
    })
    return items
  }, [t, user?.role])

  const selectedKey =
    menuItems.find(
      (item) => item.key !== '/' && location.pathname.startsWith(item.key),
    )?.key ?? '/'

  const changeLanguage = (lng: string) => {
    void i18n.changeLanguage(lng)
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lng)
  }

  const onLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider breakpoint="lg" collapsedWidth="0">
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
            gap: 12,
            paddingInline: 16,
          }}
        >
          {user && (
            <Space size={8} wrap>
              <Typography.Text strong>
                {user.org_name || user.org_id || '—'}
              </Typography.Text>
              <Tag color="blue">{t(`role.${user.role}`)}</Tag>
              {user.full_name && (
                <Typography.Text type="secondary">
                  {user.full_name}
                </Typography.Text>
              )}
            </Space>
          )}
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
          <Button
            size="small"
            icon={<LogoutOutlined />}
            onClick={onLogout}
          >
            {t('common.logout')}
          </Button>
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
