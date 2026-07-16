import { Empty, Typography } from 'antd'
import { useTranslation } from 'react-i18next'

/** Hali qurilmagan bo'limlar uchun vaqtinchalik sahifa. */
export function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation()

  return (
    <div>
      <Typography.Title level={3}>{t(titleKey)}</Typography.Title>
      <Empty description={t('common.comingSoon')} />
    </div>
  )
}
