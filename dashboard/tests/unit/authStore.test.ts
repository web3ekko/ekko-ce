import { describe, expect, it, vi } from 'vitest'
const setupStore = async () => {
  vi.resetModules()

  const storage = new Map<string, string>()
  const getItem = vi.fn((key: string) => storage.get(key) ?? null)
  const setItem = vi.fn((key: string, value: string) => {
    storage.set(key, value)
  })
  const removeItem = vi.fn((key: string) => {
    storage.delete(key)
  })

  vi.stubGlobal('localStorage', {
    getItem,
    setItem,
    removeItem,
  })

  const { useAuthStore } = await import('../../src/store/auth')
  const { useWebSocketStore } = await import('../../src/store/websocket')
  const { apiClient } = await import('../../src/services/api')

  return { useAuthStore, useWebSocketStore, apiClient, storage, getItem, setItem, removeItem }
}

describe('auth store token sync', () => {
  it('writes http client token when setting tokens', async () => {
    const { useAuthStore, setItem } = await setupStore()

    useAuthStore.getState().setTokens({ access: 'token-access', refresh: 'token-refresh' })

    expect(setItem).toHaveBeenCalledWith('ekko-auth-token', 'token-access')
  })

  it('clears http client token when tokens cleared', async () => {
    const { useAuthStore, removeItem } = await setupStore()

    useAuthStore.getState().setTokens({ access: 'token-access', refresh: 'token-refresh' })
    useAuthStore.getState().setTokens(null)

    expect(removeItem).toHaveBeenCalledWith('ekko-auth-token')
  })

  it('clears realtime notifications on logout', async () => {
    const { useAuthStore, useWebSocketStore, apiClient } = await setupStore()

    vi.spyOn(apiClient, 'logout').mockResolvedValue(undefined)

    useWebSocketStore.setState({
      connectionState: 'connected',
      isConnected: true,
      notifications: [
        {
          id: 'notif-1',
          type: 'alert',
          title: 'Alert Title',
          message: 'Alert message',
          timestamp: '2026-01-28T10:00:00Z',
          severity: 'info',
          read: false,
        },
      ],
    })

    await useAuthStore.getState().logout()

    expect(useWebSocketStore.getState().notifications).toHaveLength(0)
    expect(useWebSocketStore.getState().connectionState).toBe('disconnected')
  })
})
