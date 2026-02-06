import { describe, expect, it } from 'vitest'

import { API_ENDPOINTS } from '../../src/config/api'

describe('API endpoints', () => {
  it('uses alert-templates routes for alert template APIs', () => {
    expect(API_ENDPOINTS.ALERT_TEMPLATES.LIST).toBe('/api/alert-templates/')
    expect(API_ENDPOINTS.ALERTS.TEMPLATES).toBe('/api/alert-templates/')
    expect(API_ENDPOINTS.ALERT_TEMPLATES.DETAIL('123')).toBe('/api/alert-templates/123/')
    expect(API_ENDPOINTS.ALERTS.TEMPLATE_PREVIEW('123')).toBe('/api/alert-templates/123/preview/')
  })

  it('exposes notifications history endpoint', () => {
    expect(API_ENDPOINTS.NOTIFICATIONS.HISTORY).toBe('/api/notifications/history/')
  })
})
