import { Drawer, Empty, List, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { sitesApi } from '../../shared/api/endpoints'
import { qk } from '../../shared/api/queryKeys'
import type { SiteOut } from '../../shared/api/types'

interface Props {
  site: SiteOut | null
  onClose: () => void
}

export function OccupantsDrawer({ site, onClose }: Props) {
  const { t } = useTranslation()

  const { data = [], isLoading } = useQuery({
    queryKey: site ? qk.occupants(site.id) : ['occupants', 'none'],
    queryFn: () => sitesApi.occupants(site!.id),
    enabled: site !== null,
    refetchInterval: 15_000,
  })

  return (
    <Drawer
      open={site !== null}
      onClose={onClose}
      title={site ? `${site.name} — ${t('sites.occupants')}` : ''}
      width={360}
    >
      {data.length === 0 && !isLoading ? (
        <Empty description={t('sites.noOccupants')} />
      ) : (
        <List
          loading={isLoading}
          dataSource={data}
          renderItem={(o) => (
            <List.Item>
              <List.Item.Meta
                title={o.full_name}
                description={
                  <Typography.Text type="secondary">
                    {t('sites.enteredAt')}:{' '}
                    {new Date(o.entered_at).toLocaleString()}
                  </Typography.Text>
                }
              />
              <Tag color="green">{t('sites.inside')}</Tag>
            </List.Item>
          )}
        />
      )}
    </Drawer>
  )
}
