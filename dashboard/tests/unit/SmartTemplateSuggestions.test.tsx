import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'

import { SmartTemplateSuggestions } from '../../src/components/alerts/SmartTemplateSuggestions'

describe('SmartTemplateSuggestions', () => {
  it('renders templates and calls onSelectTemplate', async () => {
    const user = userEvent.setup()
    const templates = [
      {
        id: 'balance-threshold',
        name: 'Balance Threshold Alert',
        description: 'Notify when balance crosses a threshold',
        usage: 42,
        relevance: 95,
        variableNames: ['threshold'],
        templateType: 'wallet',
      },
    ]
    const onSelectTemplate = vi.fn()

    render(
      <MantineProvider>
        <SmartTemplateSuggestions templates={templates} onSelectTemplate={onSelectTemplate} />
      </MantineProvider>
    )

    expect(screen.getByText('Smart Template Suggestions')).toBeInTheDocument()
    expect(screen.getByText('Best Match')).toBeInTheDocument()

    await user.click(screen.getByText('Balance Threshold Alert'))
    expect(onSelectTemplate).toHaveBeenCalledTimes(1)
    expect(onSelectTemplate).toHaveBeenCalledWith(templates[0])
  })
})
