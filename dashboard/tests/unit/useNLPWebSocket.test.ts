import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { useNLPWebSocket } from '../../src/hooks/useNLPWebSocket'
import { alertsApiService } from '../../src/services/alerts-api'
import { websocketService } from '../../src/services/websocket'

vi.mock('../../src/services/alerts-api', () => ({
  alertsApiService: {
    parseNaturalLanguageJob: vi.fn(),
    getParseResult: vi.fn(),
  },
}))

vi.mock('../../src/services/websocket', () => ({
  websocketService: {
    on: vi.fn(() => () => {}),
  },
}))

describe('useNLPWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.resetAllMocks()
  })

  it('delays fallback parse result lookup to the configured timeout', async () => {
    const timeoutSpy = vi.spyOn(globalThis, 'setTimeout')

    vi.mocked(alertsApiService.parseNaturalLanguageJob).mockResolvedValue({
      success: true,
      job_id: 'job-1',
    })
    vi.mocked(alertsApiService.getParseResult).mockResolvedValue({
      status: 'not_found',
      job_id: 'job-1',
      error: 'not ready',
    })

    const { result } = renderHook(() => useNLPWebSocket())

    await act(async () => {
      await result.current.submitJob('alert me when balance > 1')
    })

    const delays = timeoutSpy.mock.calls.map((call) => call[1]).filter((delay) => typeof delay === 'number')
    expect(delays).toContain(90000)
  })
})
