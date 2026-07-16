import { useMemo, useState } from 'react'
import {
  PlusOutlined,
  ReloadOutlined,
  UploadOutlined,
  UserAddOutlined,
} from '@ant-design/icons'
import {
  Button,
  Card,
  Input,
  Space,
  Table,
  Tag,
  TreeSelect,
  Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  departmentsApi,
  locationsApi,
  sitesApi,
  usersApi,
} from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { UserOut } from '../../shared/api/types'
import { useAuthStore } from '../../shared/auth/store'
import { canManageUsers } from '../../shared/auth/roles'
import {
  buildDepartmentMap,
  buildDepartmentTree,
} from '../../shared/utils/departments'
import { CreateUserModal } from './CreateUserModal'
import { ImportUsersModal } from './ImportUsersModal'
import { InviteModal } from './InviteModal'

const STATUS_COLORS: Record<string, string> = {
  active: 'green',
  invited: 'blue',
  pending: 'gold',
  disabled: 'red',
  suspended: 'red',
}

export function EmployeesPage() {
  const { t } = useTranslation()
  const role = useAuthStore((s) => s.user?.role)
  const canManage = canManageUsers(role)

  const [search, setSearch] = useState('')
  const [deptFilter, setDeptFilter] = useState<string | undefined>()
  const [createOpen, setCreateOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [inviteUser, setInviteUser] = useState<UserOut | null>(null)

  const usersQuery = useQuery({
    queryKey: qk.users({ department_id: deptFilter }),
    queryFn: () => usersApi.list({ department_id: deptFilter }),
  })
  const { data: departments = [] } = useQuery({
    queryKey: qk.departments,
    queryFn: departmentsApi.list,
  })
  const { data: sites = [] } = useQuery({
    queryKey: qk.sites,
    queryFn: sitesApi.list,
  })
  const { data: lastLoc } = useQuery({
    queryKey: qk.lastLocations,
    queryFn: locationsApi.last,
  })

  const deptMap = useMemo(() => buildDepartmentMap(departments), [departments])
  const siteMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const s of sites) m[s.id] = s.name
    return m
  }, [sites])
  const userSiteMap = useMemo(() => {
    const m: Record<string, string | null> = {}
    for (const p of lastLoc?.points ?? []) m[p.user_id] = p.site_id
    return m
  }, [lastLoc])

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase()
    const list = usersQuery.data ?? []
    if (!q) return list
    return list.filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.phone.toLowerCase().includes(q),
    )
  }, [usersQuery.data, search])

  const columns: TableColumnsType<UserOut> = [
    {
      title: t('employees.name'),
      dataIndex: 'full_name',
      key: 'full_name',
      sorter: (a, b) => a.full_name.localeCompare(b.full_name),
    },
    { title: t('employees.phone'), dataIndex: 'phone', key: 'phone' },
    {
      title: t('employees.role'),
      dataIndex: 'role',
      key: 'role',
      render: (r: UserOut['role']) => <Tag>{t(`role.${r}`)}</Tag>,
    },
    {
      title: t('employees.department'),
      dataIndex: 'department_id',
      key: 'department_id',
      render: (id: string | null) => (id ? (deptMap[id] ?? id) : '—'),
    },
    {
      title: t('employees.status'),
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLORS[s] ?? 'default'}>{s}</Tag>
      ),
    },
    {
      title: t('employees.currentSite'),
      key: 'current_site',
      render: (_v, row) => {
        const siteId = userSiteMap[row.id]
        return siteId ? (
          <Tag color="green">{siteMap[siteId] ?? siteId}</Tag>
        ) : (
          '—'
        )
      },
    },
  ]

  if (canManage) {
    columns.push({
      title: t('employees.actions'),
      key: 'actions',
      width: 120,
      render: (_v, row) => (
        <Button
          size="small"
          icon={<UserAddOutlined />}
          onClick={() => setInviteUser(row)}
        >
          {t('employees.invite')}
        </Button>
      ),
    })
  }

  return (
    <Card style={{ flex: 1 }} styles={{ body: { padding: 16 } }}>
      <Space
        style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}
        wrap
      >
        <Space wrap>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {t('menu.employees')}
          </Typography.Title>
          <Input.Search
            allowClear
            placeholder={t('employees.searchPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 220 }}
          />
          <TreeSelect
            allowClear
            style={{ width: 220 }}
            placeholder={t('employees.filterDepartment')}
            value={deptFilter}
            onChange={(v) => setDeptFilter(v)}
            treeData={buildDepartmentTree(departments)}
            treeDefaultExpandAll
          />
        </Space>
        <Space wrap>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void usersQuery.refetch()}
          />
          {canManage && (
            <>
              <Button
                icon={<UploadOutlined />}
                onClick={() => setImportOpen(true)}
              >
                {t('employees.import')}
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setCreateOpen(true)}
              >
                {t('employees.create')}
              </Button>
            </>
          )}
        </Space>
      </Space>

      <Table<UserOut>
        rowKey="id"
        loading={usersQuery.isLoading}
        dataSource={rows}
        columns={columns}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        scroll={{ x: 'max-content' }}
      />

      <CreateUserModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <ImportUsersModal open={importOpen} onClose={() => setImportOpen(false)} />
      <InviteModal
        open={inviteUser !== null}
        user={inviteUser}
        onClose={() => setInviteUser(null)}
      />
    </Card>
  )
}
