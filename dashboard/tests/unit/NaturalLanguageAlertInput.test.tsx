import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

const navigateSpy = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigateSpy }
})

import { NaturalLanguageAlertInput } from '../../src/components/dashboard/NaturalLanguageAlertInput'

describe('NaturalLanguageAlertInput', () => {
  it('navigates to the marketplace when the browse templates button is clicked', async () => {
    const user = userEvent.setup()

    render(
      <MantineProvider>
        <NaturalLanguageAlertInput />
      </MantineProvider>
    )

    await user.click(screen.getByLabelText('Browse marketplace templates'))
    expect(navigateSpy).toHaveBeenCalledWith('/dashboard/marketplace')
  })
})
