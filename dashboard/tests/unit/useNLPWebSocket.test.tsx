import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'

vi.mock('../../src/services/websocket', () => ({
  websocketService: {
    on: vi.fn(() => () => {}),
  },
}))

vi.mock('../../src/services/alerts-api', () => ({
  alertsApiService: {
    parseNaturalLanguageJob: vi.fn(),
    getParseResult: vi.fn(),
  },
}))

describe('useNLPWebSocket', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('dedupes in-flight submissions with the same fingerprint', async () => {
    const { useNLPWebSocket } = await import('../../src/hooks/useNLPWebSocket')
    const { alertsApiService } = await import('../../src/services/alerts-api')

    vi.mocked(alertsApiService.parseNaturalLanguageJob).mockResolvedValue({
      success: true,
      job_id: 'job-1',
    })

    const { result, unmount } = renderHook(() => useNLPWebSocket())

    await act(async () => {
      await result.current.submitJob('alert me when balance drops', undefined, undefined, undefined, 'fp-1')
    })

    await act(async () => {
      await result.current.submitJob('alert me when balance drops', undefined, undefined, undefined, 'fp-1')
    })

    expect(alertsApiService.parseNaturalLanguageJob).toHaveBeenCalledTimes(1)
    unmount()
  })
})
