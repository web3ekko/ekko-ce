import { describe, expect, it } from 'vitest'

import { lightTheme } from '../../src/styles/light-theme'

describe('lightTheme typography', () => {
  it('defines an Ekko gray scale for text hierarchy', () => {
    const grayScale = lightTheme.colors.gray

    expect(grayScale).toHaveLength(10)
    expect(grayScale[0]).toBe('#F8FAFD')
    expect(grayScale[6]).toBe('#64748B')
    expect(grayScale[9]).toBe('#0F172A')
  })

  it('sets default text and title styling for readability', () => {
    expect(lightTheme.components?.Text?.defaultProps?.c).toBe('gray.8')

    const titleStyles =
      typeof lightTheme.components?.Title?.styles === 'function'
        ? lightTheme.components?.Title?.styles(lightTheme)
        : lightTheme.components?.Title?.styles

    expect(titleStyles?.root?.letterSpacing).toBe('-0.02em')
    expect(titleStyles?.root?.textWrap).toBe('balance')
  })
})
