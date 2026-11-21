import { watchEffect } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { getSession } from './auth/cognito'
import { locale, t } from './content/preferences'
import PortfolioView from './views/PortfolioView.vue'

const ProjectsView = () => import('./views/ProjectsView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: PortfolioView, meta: { portfolioTitle: 'Developer Portfolio' } },
    { path: '/projects', component: ProjectsView, meta: { portfolioTitle: 'Projects' } },
    { path: '/projects/:slug', name: 'project', component: ProjectsView, props: true, meta: { portfolioTitle: 'Project write-up' } },
    { path: '/about', component: () => import('./views/AboutView.vue'), meta: { portfolioTitle: 'About' } },
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { title: 'Sign in · Angel Tools' } },
    { path: '/auth/callback', component: () => import('./views/AuthCallbackView.vue'), meta: { title: 'Signing in · Angel Tools' } },
    { path: '/tools', component: () => import('./views/ToolsView.vue'), meta: { requiresAuth: true, title: 'Tools · Angel' } },
    { path: '/tools/minecraft', component: () => import('./views/MinecraftView.vue'), meta: { requiresAuth: true, title: 'Minecraft · Angel Tools' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash }
    return { top: 0 }
  },
})

router.beforeEach(async to => {
  if (!to.meta.requiresAuth) return true
  try {
    if (await getSession()) return true
  } catch {
    return { path: '/login', query: { error: 'configuration' } }
  }
  return { path: '/login' }
})
watchEffect(() => {
  const { portfolioTitle, title } = router.currentRoute.value.meta
  const language = portfolioTitle ? locale.value : 'en'
  document.documentElement.lang = language === 'pt' ? 'pt-BR' : language
  document.title = portfolioTitle ? `${t(portfolioTitle)} · Angel` : title || 'Angel · Developer Portfolio'
})
export default router
