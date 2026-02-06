/**
 * Simple Alert Management Store
 *
 * Alert state management with API integration
 */

import { create } from 'zustand'
import alertsApiService, {
  type AlertInstanceCreateRequest,
  type AlertTemplatePreviewRequest,
  type PreviewConfig,
  type PreviewResult,
} from '../services/alerts-api'
import notificationsApiService, { type NotificationHistoryItem } from '../services/notifications-api'

export interface SimpleAlert {
  id: string
  name: string
  description: string
  status: 'active' | 'paused' | 'error' | 'draft'
  event_type: string
  created_at: string
  enabled: boolean
  trigger_count: number
  last_triggered?: string
  network: string
  conditions: string // Simplified as string for now

  // Enhanced alert system fields
  alert_type?: 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft'
  target_group?: string | null
  target_group_name?: string | null
  target_group_type?: string | null
  target_keys?: string[]
  priority?: 'low' | 'normal' | 'high'
  source_type?: 'manual' | 'natural_language' | 'template'
  template_id?: string
  template_params?: Record<string, unknown>
  template_version?: number
  natural_language?: string
  confidence?: number
  specification?: any
}

export type Alert = SimpleAlert

function mapApiAlertToSimpleAlert(alert: any): SimpleAlert {
  const enabled = !!alert.enabled
  const chains = alert.chains
  const network =
    typeof chains?.[0] === 'string'
      ? chains[0]
      : (chains?.[0]?.chain_id || chains?.[0]?.network || alert.network || 'ethereum')

  return {
    id: alert.id,
    name: alert.name || 'Unnamed Alert',
    description: alert.nl_description || alert.description || '',
    status: enabled ? 'active' : 'paused',
    event_type: alert.event_type || '',
    created_at: alert.created_at || new Date().toISOString(),
    enabled,
    trigger_count: alert.trigger_count || 0,
    last_triggered: alert.last_triggered,
    network,
    conditions: alert.spec?.condition?.config?.raw || '',
    alert_type: alert.alert_type,
    target_group: alert.target_group ?? null,
    target_group_name: alert.target_group_name ?? null,
    target_group_type: alert.target_group_type ?? null,
    target_keys: Array.isArray(alert.target_keys) ? alert.target_keys : undefined,
    priority: alert.priority,
    source_type: alert.template ? 'template' : (alert.nl_description ? 'natural_language' : 'manual'),
    template_id: alert.template,
    template_params: alert.template_params,
    template_version: alert.template_version,
    natural_language: alert.nl_description,
    specification: alert.spec,
  }
}

function applyNotificationHistory(alerts: SimpleAlert[], historyItems: NotificationHistoryItem[]): SimpleAlert[] {
  if (!historyItems.length) return alerts

  const stats = new Map<string, { last_triggered: string; count: number }>()
  historyItems.forEach((item) => {
    if (!item.alert_id || !item.created_at) return
    const current = stats.get(item.alert_id) || { last_triggered: item.created_at, count: 0 }
    current.count += 1
    if (new Date(item.created_at).getTime() > new Date(current.last_triggered).getTime()) {
      current.last_triggered = item.created_at
    }
    stats.set(item.alert_id, current)
  })

  return alerts.map((alert) => {
    const stat = stats.get(alert.id)
    if (!stat) return alert

    const existingLast = alert.last_triggered
    const lastTriggered =
      existingLast && new Date(existingLast).getTime() > new Date(stat.last_triggered).getTime()
        ? existingLast
        : stat.last_triggered

    return {
      ...alert,
      last_triggered: lastTriggered,
      trigger_count: Math.max(alert.trigger_count || 0, stat.count),
    }
  })
}

interface SimpleAlertState {
  // State
  alerts: SimpleAlert[]
  selectedAlerts: string[]
  isLoading: boolean
  error: string | null

  // Preview State
  previewResult: PreviewResult | null
  isPreviewLoading: boolean
  previewError: string | null

  // Actions
  loadAlerts: () => Promise<void>
  createAlert: (alert: AlertInstanceCreateRequest) => Promise<void>
  updateAlert: (id: string, updates: Partial<SimpleAlert>) => Promise<void>
  deleteAlert: (id: string) => Promise<void>
  toggleAlert: (id: string) => Promise<void>
  selectAlert: (id: string) => void
  selectAllAlerts: () => void
  clearSelection: () => void
  deleteSelectedAlerts: () => Promise<void>
  setError: (error: string | null) => void

  // Preview Actions
  runPreview: (alertId: string, config?: PreviewConfig) => Promise<void>
  runTemplatePreview: (templateId: string, config?: PreviewConfig) => Promise<void>
  runInlinePreview: (spec: Record<string, unknown>, config?: PreviewConfig, alertType?: string) => Promise<void>
  runTemplatePreviewFromJob: (request: AlertTemplatePreviewRequest) => Promise<void>
  clearPreview: () => void
}

// No mock data - start with empty alerts

export const useSimpleAlerts = create<SimpleAlertState>((set, get) => ({
  // Initial state
  alerts: [],
  selectedAlerts: [],
  isLoading: false,
  error: null,

  // Preview initial state
  previewResult: null,
  isPreviewLoading: false,
  previewError: null,

  // Load alerts from API
  loadAlerts: async () => {
    set({ isLoading: true, error: null })

    try {
      const response = await alertsApiService.getAlerts()

      let mappedAlerts: SimpleAlert[] = (response.results || []).map(mapApiAlertToSimpleAlert)

      try {
        const history = await notificationsApiService.getHistory({ limit: 200 })
        mappedAlerts = applyNotificationHistory(mappedAlerts, history.results || [])
      } catch (historyError) {
        console.warn('Failed to load notification history for trigger stats:', historyError)
      }

      set({
        alerts: mappedAlerts,
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to load alerts:', error)
      set({
        error: 'Failed to load alerts',
        isLoading: false,
      })
    }
  },

  // Create new alert via API
  // For NL-based alerts, we send only the description and let Django/NLP
  // determine the event_type, sub_event, and generate the spec
  createAlert: async (alertData) => {
    try {
      const newAlert = await alertsApiService.createAlert(alertData)

      const mappedAlert = mapApiAlertToSimpleAlert(newAlert)

      set((state) => ({
        alerts: [mappedAlert, ...state.alerts],
      }))
    } catch (error) {
      console.error('Failed to create alert:', error)
      set({ error: 'Failed to create alert' })
      throw error
    }
  },

  // Update existing alert via API
  updateAlert: async (id, updates) => {
    try {
      const apiUpdates: Record<string, unknown> = {}
      if (updates.name !== undefined) apiUpdates.name = updates.name
      if (updates.description !== undefined) apiUpdates.nl_description = updates.description
      if (updates.enabled !== undefined) apiUpdates.enabled = updates.enabled

      const updatedAlert = await alertsApiService.updateAlert(id, apiUpdates as any)
      const mapped = mapApiAlertToSimpleAlert(updatedAlert)
      set((state) => ({
        alerts: state.alerts.map((alert) => (alert.id === id ? mapped : alert)),
      }))
    } catch (error) {
      console.error('Failed to update alert:', error)
      set({ error: 'Failed to update alert' })
      throw error
    }
  },

  // Delete alert via API
  deleteAlert: async (id) => {
    try {
      await alertsApiService.deleteAlert(id)
      set((state) => ({
        alerts: state.alerts.filter((alert) => alert.id !== id),
        selectedAlerts: state.selectedAlerts.filter((selectedId) => selectedId !== id),
      }))
    } catch (error) {
      console.error('Failed to delete alert:', error)
      set({ error: 'Failed to delete alert' })
      throw error
    }
  },

  // Toggle alert enabled/disabled via API
  toggleAlert: async (id) => {
    try {
      const alert = get().alerts.find((a) => a.id === id)
      if (!alert) return

      const newEnabled = !alert.enabled
      const updatedAlert = await alertsApiService.toggleAlert(id, newEnabled)

      set((state) => ({
        alerts: state.alerts.map((a) => (a.id === id ? mapApiAlertToSimpleAlert(updatedAlert) : a)),
      }))
    } catch (error) {
      console.error('Failed to toggle alert:', error)
      set({ error: 'Failed to toggle alert' })
      throw error
    }
  },

  // Select/deselect alert
  selectAlert: (id) => {
    set(state => ({
      selectedAlerts: state.selectedAlerts.includes(id)
        ? state.selectedAlerts.filter(selectedId => selectedId !== id)
        : [...state.selectedAlerts, id]
    }))
  },

  // Select all alerts
  selectAllAlerts: () => {
    set(state => ({
      selectedAlerts: state.alerts.map(alert => alert.id)
    }))
  },

  // Clear all selections
  clearSelection: () => {
    set({ selectedAlerts: [] })
  },

  // Delete selected alerts via API
  deleteSelectedAlerts: async () => {
    try {
      const { selectedAlerts } = get()
      if (selectedAlerts.length === 0) return

      await alertsApiService.bulkDeleteAlerts(selectedAlerts)
      set((state) => ({
        alerts: state.alerts.filter((alert) => !state.selectedAlerts.includes(alert.id)),
        selectedAlerts: [],
      }))
    } catch (error) {
      console.error('Failed to delete selected alerts:', error)
      set({ error: 'Failed to delete selected alerts' })
      throw error
    }
  },

  // Set error message
  setError: (error) => {
    set({ error })
  },

  // Run preview for an existing alert
  runPreview: async (alertId, config = {}) => {
    set({ isPreviewLoading: true, previewError: null, previewResult: null })

    try {
      const result = await alertsApiService.previewAlert(alertId, config)
      set({
        previewResult: result,
        isPreviewLoading: false,
        previewError: result.success ? null : result.error || null,
      })
    } catch (error) {
      console.error('Failed to run preview:', error)
      set({
        previewError: 'Failed to run preview',
        isPreviewLoading: false,
      })
    }
  },

  // Run preview for a template with parameters
  runTemplatePreview: async (templateId, config = {}) => {
    set({ isPreviewLoading: true, previewError: null, previewResult: null })

    try {
      const result = await alertsApiService.previewTemplate(templateId, config)
      set({
        previewResult: result,
        isPreviewLoading: false,
        previewError: result.success ? null : result.error || null,
      })
    } catch (error) {
      console.error('Failed to run template preview:', error)
      set({
        previewError: 'Failed to run template preview',
        isPreviewLoading: false,
      })
    }
  },

  // Run preview with inline spec (no template_id required)
  // This is the primary flow for NL-based alert creation
  runInlinePreview: async (spec, config = {}, alertType = 'wallet') => {
    set({ isPreviewLoading: true, previewError: null, previewResult: null })

    try {
      const result = await alertsApiService.previewInline(spec, config, alertType)
      set({
        previewResult: result,
        isPreviewLoading: false,
        previewError: result.success ? null : result.error || null,
      })
    } catch (error) {
      console.error('Failed to run inline preview:', error)
      set({
        previewError: 'Failed to run inline preview',
        isPreviewLoading: false,
      })
    }
  },

  runTemplatePreviewFromJob: async (request) => {
    set({ isPreviewLoading: true, previewError: null, previewResult: null })

    try {
      const result = await alertsApiService.previewTemplateFromJob(request)
      set({
        previewResult: result,
        isPreviewLoading: false,
        previewError: result.success ? null : result.error || null,
      })
    } catch (error) {
      console.error('Failed to run template preview:', error)
      set({
        previewError: 'Failed to run preview',
        isPreviewLoading: false,
      })
    }
  },

  // Clear preview results
  clearPreview: () => {
    set({
      previewResult: null,
      isPreviewLoading: false,
      previewError: null,
    })
  },
}))
