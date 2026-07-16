import { useState } from 'react'
import { EditOutlined, PlusOutlined, TeamOutlined } from '@ant-design/icons'
import { Button, Card, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { sitesApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { SiteOut } from '../../shared/api/types'
import { useAuthStore } from '../../shared/auth/store'
import { canManageSites } from '../../shared/auth/roles'
import { OccupantsDrawer } from './OccupantsDrawer'
import { SiteModal } from './SiteModal'

export function SitesPage() {
  const { t } = useTranslation()
  const role = useAuthStore((s) => s.user?.role)
  const canManage = canManageSites(role)

  const [modalOpen, setModalOpen] = useState(false)
  const [editSite, setEditSite] = useState<SiteOut | null>(null)
  const [occSite, setOccSite] = useState<SiteOut | null>(null)

  const { data = [], isLoading } = useQuery({
    queryKey: qk.sites,
    queryFn: sitesApi.list,
  })

  const openCreate = () => {
    setEditSite(null)
    setModalOpen(true)
  }
  const openEdit = (site: SiteOut) => {
    setEditSite(site)
    setModalOpen(true)
  }

  const columns: TableColumnsType<SiteOut> = [
    { title: t('sites.name'), dataIndex: 'name', key: 'name' },
    {
      title: t('sites.address'),
      dataIndex: 'address',
      key: 'address',
      render: (a: string | null) => a ?? '—',
    },
    {
      title: t('sites.coords'),
      key: 'coords',
      render: (_v, s) => `${s.lat.toFixed(5)}, ${s.lon.toFixed(5)}`,
    },
    {
      title: t('sites.radius'),
      dataIndex: 'radius_m',
      key: 'radius_m',
      render: (r: number) => `${r} m`,
    },
    {
      title: t('sites.minDwell'),
      dataIndex: 'min_dwell_minutes',
      key: 'min_dwell_minutes',
      render: (m: number) => `${m} min`,
    },
    {
      title: t('sites.status'),
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={s === 'active' ? 'green' : 'default'}>{s}</Tag>
      ),
    },
    {
      title: t('employees.actions'),
      key: 'actions',
      render: (_v, s) => (
        <Space>
          <Button
            size="small"
            icon={<TeamOutlined />}
            onClick={() => setOccSite(s)}
          >
            {t('sites.occupants')}
          </Button>
          {canManage && (
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => openEdit(s)}
            >
              {t('common.edit')}
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Card style={{ flex: 1 }} styles={{ body: { padding: 16 } }}>
      <Space
        style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}
        wrap
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          {t('menu.sites')}
        </Typography.Title>
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            {t('sites.create')}
          </Button>
        )}
      </Space>

      <Table<SiteOut>
        rowKey="id"
        loading={isLoading}
        dataSource={data}
        columns={columns}
        pagination={{ pageSize: 20 }}
        scroll={{ x: 'max-content' }}
      />

      <SiteModal
        open={modalOpen}
        site={editSite}
        onClose={() => setModalOpen(false)}
      />
      <OccupantsDrawer site={occSite} onClose={() => setOccSite(null)} />
    </Card>
  )
}
