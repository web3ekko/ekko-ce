import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { AlertEventBadge } from '../../src/components/alerts/AlertEventBadge'

describe('AlertEventBadge', () => {
  it('renders the event label based on the event type', () => {
    render(
      <MantineProvider>
        <AlertEventBadge eventType="swap" chain="avalanche" />
      </MantineProvider>
    )

    expect(screen.getByText('Swap')).toBeInTheDocument()
  })

  it('falls back to the generic label when no match is found', () => {
    render(
      <MantineProvider>
        <AlertEventBadge eventType="unknown_event" />
      </MantineProvider>
    )

    expect(screen.getByText('Alert')).toBeInTheDocument()
  })
})
