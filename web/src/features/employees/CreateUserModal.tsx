import { App, Form, Input, Modal, Select, TreeSelect } from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { getApiErrorMessage } from '../../shared/api/client'
import { departmentsApi, usersApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { CreateUserInput, Role } from '../../shared/api/types'
import { ROLE_VALUES } from '../../shared/auth/roles'
import { buildDepartmentTree } from '../../shared/utils/departments'

interface Props {
  open: boolean
  onClose: () => void
}

interface FormValues {
  full_name: string
  phone: string
  role?: Role
  department_id?: string
  employee_no?: string
}

export function CreateUserModal({ open, onClose }: Props) {
  const { t } = useTranslation()
  const { message } = App.useApp()
  const [form] = Form.useForm<FormValues>()
  const queryClient = useQueryClient()

  const { data: departments = [] } = useQuery({
    queryKey: qk.departments,
    queryFn: departmentsApi.list,
    enabled: open,
  })

  const mutation = useMutation({
    mutationFn: (input: CreateUserInput) => usersApi.create(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      message.success(t('employees.created'))
      form.resetFields()
      onClose()
    },
    onError: (e) => message.error(getApiErrorMessage(e)),
  })

  const onOk = () => {
    form
      .validateFields()
      .then((values) =>
        mutation.mutate({
          full_name: values.full_name,
          phone: values.phone,
          role: values.role,
          department_id: values.department_id ?? null,
          employee_no: values.employee_no ?? null,
        }),
      )
      .catch(() => undefined)
  }

  return (
    <Modal
      open={open}
      title={t('employees.createTitle')}
      onOk={onOk}
      onCancel={onClose}
      confirmLoading={mutation.isPending}
      okText={t('common.create')}
      cancelText={t('common.cancel')}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="full_name"
          label={t('employees.name')}
          rules={[{ required: true, message: t('employees.nameRequired') }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="phone"
          label={t('employees.phone')}
          rules={[{ required: true, message: t('employees.phoneRequired') }]}
        >
          <Input placeholder="+998901234567" />
        </Form.Item>
        <Form.Item name="role" label={t('employees.role')}>
          <Select
            allowClear
            options={ROLE_VALUES.map((r) => ({
              value: r,
              label: t(`role.${r}`),
            }))}
          />
        </Form.Item>
        <Form.Item name="department_id" label={t('employees.department')}>
          <TreeSelect
            allowClear
            showSearch
            treeDefaultExpandAll
            treeNodeFilterProp="title"
            treeData={buildDepartmentTree(departments)}
            placeholder={t('employees.department')}
          />
        </Form.Item>
        <Form.Item name="employee_no" label={t('employees.employeeNo')}>
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  )
}
