import { Button, Card, Form, Input, Typography } from 'antd'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

interface LoginFormValues {
  phone: string
  otp: string
}

/**
 * Login stub: telefon + SMS-kod (OTP) formasi.
 * TODO: backend tayyor bo'lganda haqiqiy oqim ulanadi —
 * POST /auth/otp/request → POST /auth/otp/verify, qaytgan JWT
 * localStorage'dagi ACCESS_TOKEN_KEY'ga yoziladi (shared/api/client.ts o'qiydi).
 */
export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  const onFinish = (_values: LoginFormValues) => {
    navigate('/')
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Card style={{ width: 360 }}>
        <Typography.Title level={3} style={{ textAlign: 'center' }}>
          {t('login.title')}
        </Typography.Title>
        <Form<LoginFormValues> layout="vertical" onFinish={onFinish}>
          <Form.Item
            name="phone"
            label={t('login.phone')}
            rules={[{ required: true, message: t('login.phoneRequired') }]}
          >
            <Input placeholder="+998 90 123 45 67" autoComplete="tel" />
          </Form.Item>
          <Form.Item
            name="otp"
            label={t('login.otp')}
            rules={[{ required: true, message: t('login.otpRequired') }]}
          >
            <Input maxLength={6} autoComplete="one-time-code" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            {t('login.submit')}
          </Button>
        </Form>
      </Card>
    </div>
  )
}
