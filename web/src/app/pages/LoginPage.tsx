import { useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Descriptions,
  Divider,
  Form,
  Input,
  Segmented,
  Space,
  Typography,
} from 'antd'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate } from 'react-router-dom'
import { authApi } from '../../shared/api/endpoints'
import { getApiErrorMessage } from '../../shared/api/client'
import type { InviteResolveResponse } from '../../shared/api/types'
import { useAuthStore } from '../../shared/auth/store'

const DEVICE_FP_KEY = 'device_fingerprint'

function getDeviceFingerprint(): string {
  let fp = localStorage.getItem(DEVICE_FP_KEY)
  if (!fp) {
    fp =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2)
    localStorage.setItem(DEVICE_FP_KEY, fp)
  }
  return fp
}

type Mode = 'password' | 'token' | 'otp'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { message } = App.useApp()
  const accessToken = useAuthStore((s) => s.accessToken)
  const setSession = useAuthStore((s) => s.setSession)
  const patchUser = useAuthStore((s) => s.patchUser)
  const logout = useAuthStore((s) => s.logout)

  const [mode, setMode] = useState<Mode>('password')

  // --- username/parol oqimi (asosiy — rahbar/HR/admin shu bilan kiradi) ---
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  // --- token oqimi ---
  const [tokenValue, setTokenValue] = useState('')
  const [refreshValue, setRefreshValue] = useState('')
  const [tokenLoading, setTokenLoading] = useState(false)

  // --- OTP oqimi ---
  const [inviteToken, setInviteToken] = useState('')
  const [resolved, setResolved] = useState<InviteResolveResponse | null>(null)
  const [devCode, setDevCode] = useState<string | null>(null)
  const [otpCode, setOtpCode] = useState('')
  const [otpBusy, setOtpBusy] = useState(false)

  if (accessToken) return <Navigate to="/" replace />

  const submitPassword = async () => {
    const u = username.trim()
    if (!u) {
      message.error(t('login.usernameRequired'))
      return
    }
    if (!password) {
      message.error(t('login.passwordRequired'))
      return
    }
    setPwLoading(true)
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
      setPwLoading(false)
    }
  }

  const submitToken = async () => {
    const token = tokenValue.trim()
    if (!token) {
      message.error(t('login.tokenRequired'))
      return
    }
    setTokenLoading(true)
    try {
      setSession({
        accessToken: token,
        refreshToken: refreshValue.trim() || undefined,
      })
      // Token'ni /me bilan tekshiramiz va full_name'ni to'ldiramiz.
      const me = await authApi.me()
      patchUser({ full_name: me.full_name, role: me.role, org_id: me.org_id })
      message.success(t('login.success'))
      navigate('/', { replace: true })
    } catch (e) {
      logout()
      message.error(getApiErrorMessage(e, t('login.tokenInvalid')))
    } finally {
      setTokenLoading(false)
    }
  }

  const resolveInvite = async () => {
    const token = inviteToken.trim()
    if (!token) {
      message.error(t('login.inviteRequired'))
      return
    }
    setOtpBusy(true)
    try {
      const res = await authApi.resolveInvite(token)
      setResolved(res)
      setDevCode(null)
      setOtpCode('')
    } catch (e) {
      setResolved(null)
      message.error(getApiErrorMessage(e, t('login.inviteInvalid')))
    } finally {
      setOtpBusy(false)
    }
  }

  const requestOtp = async () => {
    setOtpBusy(true)
    try {
      const res = await authApi.requestOtp(inviteToken.trim())
      if (res.dev_code) {
        setDevCode(res.dev_code)
        setOtpCode(res.dev_code)
      }
      message.success(t('login.otpSent'))
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setOtpBusy(false)
    }
  }

  const activate = async () => {
    const code = otpCode.trim()
    if (!code) {
      message.error(t('login.otpRequired'))
      return
    }
    setOtpBusy(true)
    try {
      const res = await authApi.activate({
        token: inviteToken.trim(),
        otp_code: code,
        device: {
          platform: 'web',
          fingerprint: getDeviceFingerprint(),
          model: 'web-admin',
        },
      })
      setSession({
        accessToken: res.access_token,
        refreshToken: res.refresh_token,
        user: {
          id: res.user.id,
          role: res.user.role,
          org_id: res.user.org_id,
          org_name: res.user.org_name,
        },
      })
      message.success(t('login.success'))
      navigate('/', { replace: true })
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setOtpBusy(false)
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

        <Segmented<Mode>
          block
          value={mode}
          onChange={setMode}
          options={[
            { value: 'password', label: t('login.modePassword') },
            { value: 'token', label: t('login.modeToken') },
            { value: 'otp', label: t('login.modeOtp') },
          ]}
          style={{ marginBottom: 16 }}
        />

        {mode === 'password' ? (
          <Form
            layout="vertical"
            onFinish={submitPassword}
            disabled={pwLoading}
          >
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
                onPressEnter={submitPassword}
              />
            </Form.Item>
            <Button type="primary" block htmlType="submit" loading={pwLoading}>
              {t('login.submit')}
            </Button>
          </Form>
        ) : mode === 'token' ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert type="info" showIcon message={t('login.tokenHint')} />
            <div>
              <Typography.Text strong>{t('login.accessToken')}</Typography.Text>
              <Input.TextArea
                rows={4}
                value={tokenValue}
                onChange={(e) => setTokenValue(e.target.value)}
                placeholder="eyJhbGciOi..."
                autoComplete="off"
              />
            </div>
            <div>
              <Typography.Text type="secondary">
                {t('login.refreshTokenOptional')}
              </Typography.Text>
              <Input
                value={refreshValue}
                onChange={(e) => setRefreshValue(e.target.value)}
                placeholder="(ixtiyoriy)"
                autoComplete="off"
              />
            </div>
            <Button
              type="primary"
              block
              loading={tokenLoading}
              onClick={submitToken}
            >
              {t('login.submit')}
            </Button>
          </Space>
        ) : (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Form layout="vertical">
              <Form.Item label={t('login.inviteToken')} style={{ marginBottom: 8 }}>
                <Input
                  value={inviteToken}
                  onChange={(e) => setInviteToken(e.target.value)}
                  placeholder={t('login.inviteToken')}
                  autoComplete="off"
                />
              </Form.Item>
              <Button block loading={otpBusy} onClick={resolveInvite}>
                {t('login.resolve')}
              </Button>
            </Form>

            {resolved && (
              <>
                <Descriptions size="small" column={1} bordered>
                  <Descriptions.Item label={t('login.org')}>
                    {resolved.org_name}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('login.phone')}>
                    {resolved.masked_phone}
                  </Descriptions.Item>
                </Descriptions>
                <Button block loading={otpBusy} onClick={requestOtp}>
                  {t('login.requestOtp')}
                </Button>
                {devCode && (
                  <Alert
                    type="success"
                    showIcon
                    message={`${t('login.devCode')}: ${devCode}`}
                  />
                )}
                <Divider style={{ margin: '4px 0' }} />
                <Input
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  maxLength={6}
                  placeholder={t('login.otp')}
                  autoComplete="one-time-code"
                />
                <Button
                  type="primary"
                  block
                  loading={otpBusy}
                  onClick={activate}
                >
                  {t('login.activate')}
                </Button>
              </>
            )}
          </Space>
        )}
      </Card>
    </div>
  )
}
