import { ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import uzUZ from 'antd/locale/uz_UZ'
import { useTranslation } from 'react-i18next'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'

export function App() {
  // Til o'zgarganda AntD locale ham birga almashadi
  const { i18n } = useTranslation()

  return (
    <ConfigProvider locale={i18n.language === 'ru' ? ruRU : uzUZ}>
      <RouterProvider router={router} />
    </ConfigProvider>
  )
}
