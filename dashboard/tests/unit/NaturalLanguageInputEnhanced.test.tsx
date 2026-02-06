import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'

import { NaturalLanguageInputEnhanced } from '../../src/components/alerts/NaturalLanguageInputEnhanced'

describe('NaturalLanguageInputEnhanced', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders the processing indicator outside the textarea', () => {
    const handleChange = vi.fn()

    render(
      <MantineProvider>
        <NaturalLanguageInputEnhanced
          value="Alert me when balances change"
          onChange={handleChange}
          isProcessing
        />
      </MantineProvider>
    )

    const textarea = screen.getByRole('textbox')
    const surface = screen.getByTestId('nlp-input-surface')
    const indicator = screen.getByTestId('nlp-processing-indicator')

    expect(indicator).toHaveTextContent('Understanding...')
    expect(textarea).not.toContainElement(indicator)
    expect(surface).not.toContainElement(indicator)
    expect(indicator.compareDocumentPosition(surface) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('hides the processing indicator when not processing', () => {
    render(
      <MantineProvider>
        <NaturalLanguageInputEnhanced value="" onChange={() => {}} isProcessing={false} />
      </MantineProvider>
    )

    expect(screen.queryByTestId('nlp-processing-indicator')).not.toBeInTheDocument()
  })
})
