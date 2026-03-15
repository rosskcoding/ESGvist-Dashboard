import '@testing-library/jest-dom'
import { beforeAll } from 'vitest'
import i18n, { i18nReady } from './i18n'

beforeAll(async () => {
  await i18nReady
  await i18n.changeLanguage('en')
})
