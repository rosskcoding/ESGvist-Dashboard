import i18n, { type Resource } from 'i18next'
import { initReactI18next } from 'react-i18next'

const localeModules = import.meta.glob('./locales/*/*.json', { eager: true }) as Record<
  string,
  { default: Record<string, unknown> }
>

const localeResources: Record<string, Record<string, unknown>> = {}

for (const [modulePath, moduleValue] of Object.entries(localeModules)) {
  const match = modulePath.match(/^\.\/locales\/([^/]+)\/([^/]+)\.json$/)
  if (!match) continue

  const [, locale, namespace] = match
  const resourcesForLocale = (localeResources[locale] ??= {})
  resourcesForLocale[namespace] = moduleValue.default
}

const defaultLanguage = 'en-GB'
const defaultNamespaces = Object.keys(localeResources[defaultLanguage] ?? {})

if (!defaultNamespaces.includes('common')) {
  throw new Error("Missing 'common' namespace in default language resources")
}

export const i18nReady = i18n.use(initReactI18next).init({
  resources: localeResources as unknown as Resource,
  lng: defaultLanguage,
  fallbackLng: defaultLanguage,
  defaultNS: 'common',
  ns: defaultNamespaces,
  // Keep initialization synchronous when resources are bundled locally.
  // This avoids rendering translation keys in tests and initial paint.
  initImmediate: false,
  interpolation: {
    escapeValue: false,
  },
  returnNull: false,
})

function applyDocumentLocale(lng: string) {
  if (typeof document === 'undefined') return
  const html = document.documentElement
  html.lang = lng
  html.dir = lng === 'ar' || lng.startsWith('ar-') ? 'rtl' : 'ltr'
}

applyDocumentLocale(i18n.language)
i18n.on('languageChanged', applyDocumentLocale)

if (import.meta.env.DEV) {
  i18n.on('missingKey', (lngs, ns, key) => {
    console.warn('[i18n] Missing key', { key, lngs, ns })
  })
}

export default i18n
