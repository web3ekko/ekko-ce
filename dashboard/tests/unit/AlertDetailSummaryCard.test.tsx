import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

import { AlertDetailSummaryCard } from '../../src/components/alerts/AlertDetailSummaryCard'

describe('AlertDetailSummaryCard', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders summary items and status badge', () => {
    render(
      <MantineProvider>
        <AlertDetailSummaryCard
          eventType="ACCOUNT_EVENT"
          subEvent="CUSTOM"
          alertType="wallet"
          targetSummary="Group · Accounts"
          processingStatus="skipped"
          enabled
          isSaving={false}
          createdAt="2025-01-01T00:00:00Z"
          updatedAt="2025-01-02T00:00:00Z"
          onToggle={() => {}}
        />
      </MantineProvider>
    )

    expect(screen.getByText('Summary')).toBeInTheDocument()
    expect(screen.getAllByText('Enabled').length).toBeGreaterThan(0)
    expect(screen.getByText('ACCOUNT_EVENT')).toBeInTheDocument()
    expect(screen.getByText('CUSTOM')).toBeInTheDocument()
    expect(screen.getByText('Group · Accounts')).toBeInTheDocument()
  })

  it('calls onToggle when the switch changes', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <MantineProvider>
        <AlertDetailSummaryCard
          eventType="ACCOUNT_EVENT"
          subEvent="CUSTOM"
          alertType="wallet"
          targetSummary="Group · Accounts"
          processingStatus="skipped"
          enabled
          isSaving={false}
          onToggle={onToggle}
        />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Toggle alert enabled'))

    expect(onToggle).toHaveBeenCalledWith(false)
  })

})
