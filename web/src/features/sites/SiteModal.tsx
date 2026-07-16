import { useEffect } from 'react'
import { App, Form, Input, InputNumber, Modal } from 'antd'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../shared/api/client'
import { sitesApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { SiteOut } from '../../shared/api/types'

interface Props {
  open: boolean
  site: SiteOut | null
  onClose: () => void
}

interface FormValues {
  name: string
  lat: number
  lon: number
  radius_m: number
  min_dwell_minutes: number
  address?: string
}

export function SiteModal({ open, site, onClose }: Props) {
  const { t } = useTranslation()
  const { message } = App.useApp()
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()
  const isEdit = site !== null

  useEffect(() => {
    if (!open) return
    if (site) {
      form.setFieldsValue({
        name: site.name,
        lat: site.lat,
        lon: site.lon,
        radius_m: site.radius_m,
        min_dwell_minutes: site.min_dwell_minutes,
        address: site.address ?? undefined,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ radius_m: 150, min_dwell_minutes: 15 })
    }
  }, [open, site, form])

  const mutation = useMutation({
    mutationFn: (values: FormValues) =>
      isEdit && site
        ? sitesApi.update(site.id, values)
        : sitesApi.create(values),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.sites })
      message.success(isEdit ? t('sites.updated') : t('sites.created'))
      onClose()
    },
    onError: (e) => message.error(getApiErrorMessage(e)),
  })

  const onOk = () => {
    form
      .validateFields()
      .then((values) => mutation.mutate(values))
      .catch(() => undefined)
  }

  return (
    <Modal
      open={open}
      title={isEdit ? t('sites.editTitle') : t('sites.createTitle')}
      onOk={onOk}
      onCancel={onClose}
      confirmLoading={mutation.isPending}
      okText={isEdit ? t('common.save') : t('common.create')}
      cancelText={t('common.cancel')}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label={t('sites.name')}
          rules={[{ required: true, message: t('sites.nameRequired') }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="lat"
          label={t('sites.lat')}
          rules={[{ required: true, message: t('sites.latRequired') }]}
        >
          <InputNumber style={{ width: '100%' }} step={0.0001} min={-90} max={90} />
        </Form.Item>
        <Form.Item
          name="lon"
          label={t('sites.lon')}
          rules={[{ required: true, message: t('sites.lonRequired') }]}
        >
          <InputNumber
            style={{ width: '100%' }}
            step={0.0001}
            min={-180}
            max={180}
          />
        </Form.Item>
        <Form.Item name="radius_m" label={t('sites.radius')}>
          <InputNumber style={{ width: '100%' }} min={10} max={5000} addonAfter="m" />
        </Form.Item>
        <Form.Item name="min_dwell_minutes" label={t('sites.minDwell')}>
          <InputNumber style={{ width: '100%' }} min={0} max={1440} addonAfter="min" />
        </Form.Item>
        <Form.Item name="address" label={t('sites.address')}>
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  )
}
