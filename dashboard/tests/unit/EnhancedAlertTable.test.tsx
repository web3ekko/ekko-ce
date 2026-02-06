import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { EnhancedAlertTable } from '../../src/components/alerts/EnhancedAlertTable'

describe('EnhancedAlertTable', () => {
  it('wraps long alert names', () => {
    const longName =
      'Alert me if my wallet has more than 2 transactions in the last 24 hours on Ethereum'

    render(
      <MantineProvider>
        <EnhancedAlertTable
          alerts={[
            {
              id: 'alert-1',
              name: longName,
              description: 'Long alert name should wrap',
              status: 'active',
              network: 'ethereum',
              event_type: 'ACCOUNT_EVENT',
              last_triggered: null,
              trigger_count: 0,
              enabled: true,
            },
          ]}
          selectedAlerts={[]}
          onToggleAlert={() => {}}
          onDeleteAlert={() => {}}
          onSelectAlert={() => {}}
          onSelectAllAlerts={() => {}}
          onClearSelection={() => {}}
        />
      </MantineProvider>
    )

    const nameNode = screen.getByText(longName)
    expect(nameNode).toHaveStyle('white-space: normal')
    expect(nameNode).toHaveStyle('word-break: break-word')
  })
})
