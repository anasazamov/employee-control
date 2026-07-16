import { useMemo, useState } from 'react'
import {
  CheckOutlined,
  CloseOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Modal,
  Progress,
  Result,
  Row,
  Space,
  Tag,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../shared/api/client'
import { checkinsApi, sitesApi, usersApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { CheckinOut, CheckinVerdict, ReviewAction } from '../../shared/api/types'
import { useAuthStore } from '../../shared/auth/store'
import { canReview } from '../../shared/auth/roles'

const VERDICT_COLOR: Record<CheckinVerdict, string> = {
  pending: 'gold',
  verified: 'green',
  flagged: 'volcano',
  rejected: 'red',
}

function riskColor(score: number): string {
  if (score >= 70) return '#cf1322'
  if (score >= 40) return '#fa8c16'
  return '#52c41a'
}

export function ReviewQueuePage() {
  const { t } = useTranslation()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const queryClient = useQueryClient()

  const [target, setTarget] = useState<{
    checkin: CheckinOut
    action: ReviewAction
  } | null>(null)
  const [reason, setReason] = useState('')

  const allowed = canReview(role)

  const queueQuery = useQuery({
    queryKey: qk.reviewQueue,
    queryFn: checkinsApi.reviewQueue,
    enabled: allowed,
  })
  const { data: users = [] } = useQuery({
    queryKey: qk.users(),
    queryFn: () => usersApi.list(),
    enabled: allowed,
  })
  const { data: sites = [] } = useQuery({
    queryKey: qk.sites,
    queryFn: sitesApi.list,
    enabled: allowed,
  })

  const userMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const u of users) m[u.id] = u.full_name
    return m
  }, [users])
  const siteMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const s of sites) m[s.id] = s.name
    return m
  }, [sites])

  const mutation = useMutation({
    mutationFn: (input: {
      id: string
      action: ReviewAction
      reason: string
    }) =>
      checkinsApi.review(input.id, {
        action: input.action,
        reason: input.reason,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.reviewQueue })
      message.success(t('review.done'))
      setTarget(null)
      setReason('')
    },
    onError: (e) => message.error(getApiErrorMessage(e)),
  })

  if (!allowed) {
    return <Result status="403" title={t('common.noAccess')} />
  }

  const confirmReview = () => {
    if (!target) return
    mutation.mutate({
      id: target.checkin.id,
      action: target.action,
      reason: reason.trim(),
    })
  }

  return (
    <Card style={{ flex: 1 }} styles={{ body: { padding: 16 } }}>
      <Space
        style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}
        wrap
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t('menu.review')}
        </Typography.Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void queueQuery.refetch()}
        />
      </Space>

      {queueQuery.data && queueQuery.data.length === 0 ? (
        <Empty description={t('review.empty')} />
      ) : (
        <List
          loading={queueQuery.isLoading}
          grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 2, xl: 3 }}
          dataSource={queueQuery.data ?? []}
          renderItem={(c) => (
            <List.Item>
              <Card
                size="small"
                title={
                  <Space>
                    <span>{userMap[c.user_id] ?? c.user_id}</span>
                    <Tag color={VERDICT_COLOR[c.verdict]}>
                      {t(`verdict.${c.verdict}`)}
                    </Tag>
                  </Space>
                }
              >
                <Row gutter={12} align="middle">
                  <Col flex="80px" style={{ textAlign: 'center' }}>
                    <Progress
                      type="dashboard"
                      size={64}
                      percent={Math.min(100, c.risk_score)}
                      format={() => c.risk_score}
                      strokeColor={riskColor(c.risk_score)}
                    />
                    <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                      {t('review.risk')}
                    </div>
                  </Col>
                  <Col flex="auto">
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Typography.Text type="secondary">
                        {new Date(c.ts).toLocaleString()}
                      </Typography.Text>
                      <Typography.Text>
                        {t('sites.name')}:{' '}
                        {c.site_id ? (siteMap[c.site_id] ?? c.site_id) : '—'}
                      </Typography.Text>
                      <Tag color={c.inside_geofence ? 'green' : 'red'}>
                        {c.inside_geofence
                          ? t('review.insideGeofence')
                          : t('review.outsideGeofence')}
                      </Tag>
                      {c.verdict_reasons.length > 0 && (
                        <div>
                          {c.verdict_reasons.map((r) => (
                            <Tag key={r} color="orange" style={{ marginTop: 4 }}>
                              {r}
                            </Tag>
                          ))}
                        </div>
                      )}
                    </Space>
                  </Col>
                </Row>
                <Space style={{ marginTop: 12 }}>
                  <Button
                    type="primary"
                    icon={<CheckOutlined />}
                    onClick={() => {
                      setReason('')
                      setTarget({ checkin: c, action: 'approve' })
                    }}
                  >
                    {t('review.approve')}
                  </Button>
                  <Button
                    danger
                    icon={<CloseOutlined />}
                    onClick={() => {
                      setReason('')
                      setTarget({ checkin: c, action: 'reject' })
                    }}
                  >
                    {t('review.reject')}
                  </Button>
                </Space>
              </Card>
            </List.Item>
          )}
        />
      )}

      <Modal
        open={target !== null}
        title={
          target?.action === 'approve'
            ? t('review.approve')
            : t('review.reject')
        }
        onOk={confirmReview}
        onCancel={() => setTarget(null)}
        confirmLoading={mutation.isPending}
        okText={t('common.confirm')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: target?.action === 'reject' }}
      >
        <Typography.Paragraph type="secondary">
          {t('review.reasonHint')}
        </Typography.Paragraph>
        <Input.TextArea
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={t('review.reasonPlaceholder')}
        />
      </Modal>
    </Card>
  )
}
