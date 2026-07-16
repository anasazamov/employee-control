import { useState } from 'react'
import { InboxOutlined } from '@ant-design/icons'
import { App, Alert, Modal, Space, Statistic, Table, Typography, Upload } from 'antd'
import type { UploadProps } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../shared/api/client'
import { usersApi } from '../../shared/api/endpoints'
import type { ImportResult, ImportRowResult } from '../../shared/api/types'

interface Props {
  open: boolean
  onClose: () => void
}

export function ImportUsersModal({ open, onClose }: Props) {
  const { t } = useTranslation()
  const { message } = App.useApp()
  const queryClient = useQueryClient()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)

  const doImport = async (file: File) => {
    setLoading(true)
    setResult(null)
    try {
      const res = await usersApi.import(file)
      setResult(res)
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      message.success(t('employees.importDone'))
    } catch (e) {
      message.error(getApiErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const uploadProps: UploadProps = {
    accept: '.csv',
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      void doImport(file)
      return false // avtomatik yuklamaymiz — o'zimiz jo'natamiz
    },
  }

  const columns = [
    { title: t('employees.importRow'), dataIndex: 'row', key: 'row', width: 80 },
    { title: t('employees.importStatus'), dataIndex: 'status', key: 'status', width: 120 },
    { title: t('employees.importDetail'), dataIndex: 'detail', key: 'detail' },
  ]

  return (
    <Modal
      open={open}
      title={t('employees.importTitle')}
      onCancel={onClose}
      footer={null}
      width={640}
      destroyOnHidden
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Alert
          type="info"
          showIcon
          message={t('employees.importColumns')}
          description="full_name, phone, [role], [department_path], [employee_no]"
        />
        <Upload.Dragger {...uploadProps} disabled={loading}>
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">{t('employees.importHint')}</p>
        </Upload.Dragger>

        {result && (
          <>
            <Space size="large">
              <Statistic title={t('employees.importTotal')} value={result.total} />
              <Statistic
                title={t('employees.importCreated')}
                value={result.created}
                valueStyle={{ color: '#52c41a' }}
              />
              <Statistic
                title={t('employees.importErrors')}
                value={result.errors}
                valueStyle={{ color: result.errors ? '#cf1322' : undefined }}
              />
            </Space>
            <Table<ImportRowResult>
              size="small"
              rowKey={(r) => String(r.row)}
              dataSource={result.rows}
              columns={columns}
              pagination={{ pageSize: 8, hideOnSinglePage: true }}
              scroll={{ y: 240 }}
            />
          </>
        )}
        {loading && (
          <Typography.Text type="secondary">
            {t('employees.importProcessing')}
          </Typography.Text>
        )}
      </Space>
    </Modal>
  )
}
