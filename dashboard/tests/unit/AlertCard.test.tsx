import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { AlertCard } from '../../src/components/alerts/AlertCard'
import type { Alert } from '../../src/store/simple-alerts'

const buildAlert = (overrides: Partial<Alert> = {}): Alert => ({
  id: 'alert-1',
  name: 'Alert me if my wallet has more than 2 transactions in the last 24 hours on Ethereum',
  description: 'Sample description',
  status: 'active',
  event_type: 'ACCOUNT_EVENT',
  created_at: '2026-01-28T00:00:00Z',
  enabled: true,
  trigger_count: 0,
  network: 'ethereum',
  conditions: '',
  ...overrides,
})

describe('AlertCard', () => {
  it('wraps long alert titles', () => {
    const alert = buildAlert()

    render(
      <MantineProvider>
        <AlertCard
          alert={alert}
          onToggle={() => Promise.resolve()}
          onEdit={() => {}}
          onDelete={() => {}}
          onDuplicate={() => {}}
        />
      </MantineProvider>
    )

    const title = screen.getByText(alert.name)
    expect(title).toHaveStyle('white-space: normal')
    expect(title).toHaveStyle('word-break: break-word')
  })
})
