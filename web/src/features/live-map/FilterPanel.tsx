import { Card, Checkbox, Divider, Select, Tree, Typography } from 'antd'
import type { Key } from 'react'
import { useTranslation } from 'react-i18next'
import type { DepartmentOut, UserOut } from '../../shared/api/types'
import type { MarkerStatus } from '../../shared/map/geo'
import { buildDepartmentTree } from '../../shared/utils/departments'

export interface LiveFilters {
  departmentIds: string[]
  userIds: string[]
  statuses: MarkerStatus[]
}

interface Props {
  departments: DepartmentOut[]
  users: UserOut[]
  value: LiveFilters
  onChange: (next: LiveFilters) => void
}

const STATUS_OPTIONS: MarkerStatus[] = ['on_site', 'moving', 'stale']

export function FilterPanel({ departments, users, value, onChange }: Props) {
  const { t } = useTranslation()

  return (
    <Card
      size="small"
      style={{ width: 280, overflow: 'auto' }}
      styles={{ body: { padding: 12 } }}
    >
      <Typography.Text strong>{t('map.filters')}</Typography.Text>

      <Divider style={{ margin: '8px 0' }} />
      <Typography.Text type="secondary">{t('map.status')}</Typography.Text>
      <Checkbox.Group
        style={{ display: 'flex', flexDirection: 'column', marginTop: 8 }}
        value={value.statuses}
        onChange={(vals) =>
          onChange({ ...value, statuses: vals as MarkerStatus[] })
        }
        options={STATUS_OPTIONS.map((s) => ({
          value: s,
          label: t(`map.statusLabel.${s}`),
        }))}
      />

      <Divider style={{ margin: '8px 0' }} />
      <Typography.Text type="secondary">{t('map.departments')}</Typography.Text>
      {departments.length > 0 ? (
        <Tree
          checkable
          selectable={false}
          defaultExpandAll
          style={{ marginTop: 8 }}
          treeData={buildDepartmentTree(departments)}
          checkedKeys={value.departmentIds}
          onCheck={(checked) => {
            const keys = (
              Array.isArray(checked) ? checked : checked.checked
            ) as Key[]
            onChange({ ...value, departmentIds: keys.map(String) })
          }}
        />
      ) : (
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          —
        </Typography.Text>
      )}

      <Divider style={{ margin: '8px 0' }} />
      <Typography.Text type="secondary">{t('map.employees')}</Typography.Text>
      <Select
        mode="multiple"
        allowClear
        style={{ width: '100%', marginTop: 8 }}
        placeholder={t('map.employees')}
        value={value.userIds}
        onChange={(vals) => onChange({ ...value, userIds: vals })}
        optionFilterProp="label"
        options={users.map((u) => ({ value: u.id, label: u.full_name }))}
        maxTagCount="responsive"
      />
    </Card>
  )
}
