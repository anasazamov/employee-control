import { useEffect, useState } from 'react'
import { App, Button, Modal, Result, Space, Spin, Typography } from 'antd'
import { QRCodeSVG } from 'qrcode.react'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../shared/api/client'
import { usersApi } from '../../shared/api/endpoints'
import type { InviteResult, UserOut } from '../../shared/api/types'

interface Props {
  open: boolean
  user: UserOut | null
  onClose: () => void
}

export function InviteModal({ open, user, onClose }: Props) {
  const { t } = useTranslation()
  const { message } = App.useApp()
  const [loading, setLoading] = useState(false)
  const [invite, setInvite] = useState<InviteResult | null>(null)

  useEffect(() => {
    if (!open || !user) return
    let cancelled = false
    setInvite(null)
    setLoading(true)
    usersApi
      .invite(user.id)
      .then((res) => {
        if (!cancelled) setInvite(res)
      })
      .catch((e) => {
        if (!cancelled) message.error(getApiErrorMessage(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, user, message])

  return (
    <Modal
      open={open}
      title={t('employees.inviteTitle')}
      onCancel={onClose}
      footer={
        <Button type="primary" onClick={onClose}>
          {t('common.close')}
        </Button>
      }
      destroyOnHidden
    >
      {loading && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin />
        </div>
      )}
      {!loading && invite && (
        <Space
          direction="vertical"
          align="center"
          style={{ width: '100%' }}
          size="middle"
        >
          <Typography.Text type="secondary">
            {user?.full_name}
          </Typography.Text>
          {/* QR — mobil ilova aktivatsiya-token'ni skanerlaydi. */}
          <QRCodeSVG value={invite.token} size={200} includeMargin />
          <Space direction="vertical" align="center" size={4}>
            <Typography.Text type="secondary">
              {t('employees.inviteCode')}
            </Typography.Text>
            <Typography.Title level={3} copyable style={{ margin: 0 }}>
              {invite.code}
            </Typography.Title>
          </Space>
          <Typography.Text
            type="secondary"
            copyable={{ text: invite.token }}
            style={{ fontSize: 12, wordBreak: 'break-all' }}
          >
            {t('employees.inviteToken')}: {invite.token}
          </Typography.Text>
        </Space>
      )}
      {!loading && !invite && (
        <Result status="warning" title={t('employees.inviteFailed')} />
      )}
    </Modal>
  )
}
