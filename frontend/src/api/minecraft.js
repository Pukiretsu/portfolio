import { getSession } from '../auth/cognito'

let endpoint
export async function minecraftRequest(path, { method = 'GET', body, signal } = {}) {
  const user = await getSession()
  if (!user) throw new Error('Your session has expired. Sign in again to use the launcher.')
  if (!endpoint) {
    const response = await fetch('/auth-config.json', { cache: 'no-store', signal })
    if (!response.ok) throw new Error('Launcher configuration is unavailable.')
    const config = await response.json()
    if (!/^https:\/\/[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com$/.test(config.minecraftApi || '')) {
      throw new Error('The Minecraft API is not configured yet. Complete the infrastructure deployment first.')
    }
    endpoint = config.minecraftApi
  }
  const response = await fetch(`${endpoint}/minecraft/${path}`, {
    method,
    headers: { Authorization: `Bearer ${user.access_token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    signal,
    cache: 'no-store',
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) throw new Error('Access denied. Sign in again with an invited Tools account.')
    throw new Error(data.message || 'The Minecraft control service is unavailable.')
  }
  return data
}
