import { useState } from 'react'
import { App, Button, Card, Form, Input, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate } from 'react-router-dom'
import { authApi } from '../../shared/api/endpoints'
import { getApiErrorMessage } from '../../shared/api/client'
import { useAuthStore } from '../../shared/auth/store'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const accessToken = useAuthStore((s) => s.accessToken)
  const setSession = useAuthStore((s) => s.setSession)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  if (accessToken) return <Navigate to="/" replace />

  const submit = async () => {
    const u = username.trim()
    if (!u) {
      message.error(t('login.usernameRequired'))
      return
    }
    if (!password) {
      message.error(t('login.passwordRequired'))
      return
    }
    setLoading(true)
    try {
      const res = await authApi.login({ username: u, password })
      setSession({
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
        user: {
          id: res.user.id,
          role: res.user.role,
          org_id: res.user.org_id,
          full_name: res.user.full_name,
        },
      })
      message.success(t('login.success'))
      navigate('/', { replace: true })
    } catch (e) {
      message.error(getApiErrorMessage(e, t('login.loginFailed')))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <Card style={{ width: 420, maxWidth: '100%' }}>
        <Typography.Title level={3} style={{ textAlign: 'center' }}>
          {t('login.title')}
        </Typography.Title>

        <Form layout="vertical" onFinish={submit} disabled={loading}>
          <Form.Item label={t('login.username')} style={{ marginBottom: 12 }}>
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t('login.username')}
              autoComplete="username"
              autoFocus
            />
          </Form.Item>
          <Form.Item label={t('login.password')} style={{ marginBottom: 16 }}>
            <Input.Password
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t('login.password')}
              autoComplete="current-password"
              onPressEnter={submit}
            />
          </Form.Item>
          <Button type="primary" block htmlType="submit" loading={loading}>
            {t('login.submit')}
          </Button>
        </Form>
      </Card>
    </div>
  )
}
