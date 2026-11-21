import { createRouter, createWebHistory } from 'vue-router'
import { getSession } from './auth/cognito'
import PortfolioView from './views/PortfolioView.vue'

const ProjectsView = () => import('./views/ProjectsView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: PortfolioView, meta: { title: 'Angel · Developer Portfolio' } },
    { path: '/projects', component: ProjectsView, meta: { title: 'Projects · Angel' } },
    { path: '/projects/:slug', name: 'project', component: ProjectsView, props: true, meta: { title: 'Project write-up · Angel' } },
    { path: '/about', component: () => import('./views/AboutView.vue'), meta: { title: 'About · Angel' } },
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
router.afterEach(to => { document.title = to.meta.title || 'Angel Portfolio' })
export default router
