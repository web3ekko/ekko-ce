import { describe, expect, it } from 'vitest'

import { resolveWebSocketUrl } from '../../src/services/websocket'

describe('resolveWebSocketUrl', () => {
  it('derives wss url from https dashboard host', () => {
    const url = resolveWebSocketUrl('', {
      protocol: 'https:',
      hostname: 'dashboard.ekko.local',
      port: '',
    } as Location)

    expect(url).toBe('wss://api.ekko.local/ws')
  })

  it('upgrades ws to wss on https pages', () => {
    const url = resolveWebSocketUrl('ws://api.ekko.local', {
      protocol: 'https:',
      hostname: 'dashboard.ekko.local',
      port: '',
    } as Location)

    expect(url).toBe('wss://api.ekko.local/ws')
  })
})
