import { reactive } from 'vue'
import { UserManager, WebStorageStateStore } from 'oidc-client-ts'

export const auth = reactive({ user: null })
let managerPromise

async function getManager() {
  if (!managerPromise) {
    managerPromise = (async () => {
      const response = await fetch('/auth-config.json', { cache: 'no-store' })
      if (!response.ok) throw new Error('Login is not configured yet. Please try again after the infrastructure deployment finishes.')
      const config = await response.json()
      if (!/^https:\/\/cognito-idp\.[a-z0-9-]+\.amazonaws\.com\/[^/]+$/.test(config.authority) ||
          !/^https:\/\/[a-z0-9-]+\.auth\.[a-z0-9-]+\.amazoncognito\.com$/.test(config.domain) ||
          !/^[a-z0-9]+$/.test(config.clientId)) {
        throw new Error('The login configuration is invalid.')
      }
      const manager = new UserManager({
        authority: config.authority,
        client_id: config.clientId,
        redirect_uri: `${window.location.origin}/auth/callback`,
        response_type: 'code',
        response_mode: 'query',
        scope: 'openid email profile',
        disablePKCE: false,
        automaticSilentRenew: false,
        monitorSession: false,
        loadUserInfo: false,
        // Keep sessions per-tab; never put tokens in URLs or localStorage.
        stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
        userStore: new WebStorageStateStore({ store: window.sessionStorage }),
      })
      manager.events.addAccessTokenExpired(() => {
        auth.user = null
        void manager.removeUser()
      })
      manager.events.addUserUnloaded(() => { auth.user = null })
      return { manager, config }
    })().catch(error => {
      managerPromise = undefined
      throw error
    })
  }
  return managerPromise
}

export async function getSession() {
  const { manager } = await getManager()
  const user = await manager.getUser()
  if (!user || user.expired) {
    await manager.removeUser()
    auth.user = null
    return null
  }
  auth.user = user
  return user
}

export async function signIn() {
  const { manager } = await getManager()
  await manager.clearStaleState()
  // oidc-client-ts generates and validates state and the PKCE verifier.
  await manager.signinRedirect({ nonce: crypto.randomUUID() })
}

export async function completeSignIn() {
  const { manager } = await getManager()
  const user = await manager.signinRedirectCallback()
  auth.user = user
  return user
}

export async function signOut() {
  const { manager, config } = await getManager()
  try {
    await manager.revokeTokens(['refresh_token'])
  } finally {
    await manager.removeUser()
    auth.user = null
    // Cognito uses logout_uri rather than the generic OIDC end-session parameters.
    const url = new URL('/logout', config.domain)
    url.searchParams.set('client_id', config.clientId)
    url.searchParams.set('logout_uri', `${window.location.origin}/login`)
    window.location.assign(url)
  }
}
