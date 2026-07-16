import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { ru } from './locales/ru'
import { uz } from './locales/uz'

export const DEFAULT_LANGUAGE = 'uz'
export const LANGUAGE_STORAGE_KEY = 'lang'

void i18n.use(initReactI18next).init({
  resources: {
    uz: { translation: uz },
    ru: { translation: ru },
  },
  lng: localStorage.getItem(LANGUAGE_STORAGE_KEY) ?? DEFAULT_LANGUAGE,
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: {
    // React o'zi XSS-dan himoya qiladi
    escapeValue: false,
  },
})

export default i18n
