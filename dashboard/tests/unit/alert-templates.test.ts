import { describe, expect, it } from 'vitest'

import { getTemplateRequiredParamIds, getTemplateTargetType, isValueProvided } from '../../src/utils/alert-templates'

describe('alert-templates utils', () => {
  it('isValueProvided handles common empty values', () => {
    expect(isValueProvided(undefined)).toBe(false)
    expect(isValueProvided(null)).toBe(false)
    expect(isValueProvided('')).toBe(false)
    expect(isValueProvided('   ')).toBe(false)
    expect(isValueProvided([])).toBe(false)

    expect(isValueProvided('x')).toBe(true)
    expect(isValueProvided(['x'])).toBe(true)
    expect(isValueProvided(0)).toBe(true)
    expect(isValueProvided(false)).toBe(true)
  })

  it('getTemplateTargetType maps anomaly templates to network', () => {
    expect(getTemplateTargetType({ template_type: 'anomaly' })).toBe('network')
    expect(getTemplateTargetType({ template_type: 'ANOMALY' })).toBe('network')
  })

  it('getTemplateRequiredParamIds excludes targeting variables', () => {
    const required = getTemplateRequiredParamIds({
      template_type: 'wallet',
      variables: [
        { id: 'wallet', required: true, type: 'string' },
        { id: 'network', required: true, type: 'string' },
        { id: 'subnet', required: true, type: 'string' },
        { id: 'threshold', required: true, type: 'number' },
        { id: 'operator', required: true, type: 'string' },
      ],
    })

    expect([...required].sort()).toEqual(['operator', 'threshold'])
  })
})

