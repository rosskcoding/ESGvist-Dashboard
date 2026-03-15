import { useTranslation } from 'react-i18next'
import styles from './LanguageSwitcher.module.css'

const ENABLE_UI_LANGUAGE_SWITCHER =
  import.meta.env.VITE_ENABLE_UI_LANGUAGE_SWITCHER === 'true'

const SUPPORTED_UI_LANGUAGES = [
  { code: 'en-GB' },
  { code: 'en' },
  { code: 'de' },
  { code: 'ru' },
  { code: 'ar' },
] as const

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation('ui')

  if (!ENABLE_UI_LANGUAGE_SWITCHER) return null

  const activeLanguage = SUPPORTED_UI_LANGUAGES.some((l) => l.code === i18n.language)
    ? i18n.language
    : (i18n.resolvedLanguage ?? 'en-GB')

  const handleChangeLanguage = async (nextLanguage: string) => {
    await i18n.changeLanguage(nextLanguage)
  }

  return (
    <div className={styles.container}>
      <label htmlFor="ui-language" className={styles.label}>
        {t('languageSwitcher.label')}
      </label>
      <select
        id="ui-language"
        className={styles.select}
        value={activeLanguage}
        onChange={(e) => void handleChangeLanguage(e.target.value)}
      >
        {SUPPORTED_UI_LANGUAGES.map((language) => (
          <option key={language.code} value={language.code}>
            {t(`languageSwitcher.languages.${language.code}`)}
          </option>
        ))}
      </select>
    </div>
  )
}
