import { ref, watchEffect } from 'vue'
import { messages } from './messages'

export const languages = { en: 'English', es: 'Español', pt: 'Português' }

function stored(key) {
  try { return localStorage.getItem(key) } catch { return null }
}

function persist(key, value) {
  try { localStorage.setItem(key, value) } catch { /* Storage is optional. */ }
}

const preferredLanguage = stored('portfolio-language') || navigator.language?.split('-')[0]
export const locale = ref(Object.hasOwn(languages, preferredLanguage) ? preferredLanguage : 'en')
export const theme = ref(document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')

export function t(text) {
  return messages[locale.value]?.get(text) ?? text
}

watchEffect(() => {
  persist('portfolio-language', locale.value)
})

watchEffect(() => {
  document.documentElement.dataset.theme = theme.value
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme.value === 'light' ? '#f7f8f1' : '#101211')
  persist('portfolio-theme', theme.value)
})
