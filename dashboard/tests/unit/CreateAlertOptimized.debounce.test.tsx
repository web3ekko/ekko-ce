import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

vi.mock('@mantine/notifications', () => ({
  notifications: {
    show: vi.fn(),
  },
}))

vi.mock('../../src/services/websocket', () => ({
  websocketService: {
    on: vi.fn(() => () => {}),
  },
}))

vi.mock('../../src/services/groups-api', () => ({
  groupsApiService: {
    getGroupsByType: vi.fn(),
  },
  GroupType: {
    WALLET: 'wallet',
  },
}))

vi.mock('../../src/services/alerts-api', () => ({
  alertsApiService: {
    parseNaturalLanguageJob: vi.fn(),
    getParseResult: vi.fn(),
    getTemplateLatest: vi.fn(),
    saveTemplateFromJob: vi.fn(),
  },
}))

describe('CreateAlertOptimized NLP debounce', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    })

    const { groupsApiService } = await import('../../src/services/groups-api')
    vi.mocked(groupsApiService.getGroupsByType).mockResolvedValue({ results: [] })

    const { alertsApiService } = await import('../../src/services/alerts-api')
    vi.mocked(alertsApiService.parseNaturalLanguageJob).mockResolvedValue({
      success: true,
      job_id: 'job-1',
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('debounces NLP parse calls and ignores trailing punctuation changes', async () => {
    const { CreateAlertOptimized } = await import('../../src/components/alerts/CreateAlertOptimized')
    const { alertsApiService } = await import('../../src/services/alerts-api')

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

    const { unmount } = render(
      <MantineProvider>
        <CreateAlertOptimized onAlertCreated={() => {}} onCancel={() => {}} />
      </MantineProvider>
    )

    const input = screen.getAllByRole('textbox')[0]
    await user.type(input, 'Alert me when balance drops below 10')

    expect(alertsApiService.parseNaturalLanguageJob).toHaveBeenCalledTimes(0)

    await vi.advanceTimersByTimeAsync(1500)
    expect(alertsApiService.parseNaturalLanguageJob).toHaveBeenCalledTimes(1)

    await user.type(input, '.')
    await vi.advanceTimersByTimeAsync(1500)
    expect(alertsApiService.parseNaturalLanguageJob).toHaveBeenCalledTimes(1)

    unmount()
  })
})
