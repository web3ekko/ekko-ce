/**
 * Alert Management Store
 * 
 * Global state management for alerts using Zustand
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type {
  Alert,
  AlertTemplate,
  AlertFilters,
  AlertSortOptions,
  CreateAlertRequest,
  UpdateAlertRequest,
  NotificationChannel,
} from '../types/alerts'
import { alertApiService } from '../services/alerts'

interface AlertStore {
  // State
  alerts: Alert[]
  templates: AlertTemplate[]
  channels: NotificationChannel[]
  selectedAlerts: string[]
  currentAlert: Alert | null
  
  // UI state
  isLoading: boolean
  error: string | null
  filters: AlertFilters
  sort: AlertSortOptions
  pagination: {
    page: number
    perPage: number
    total: number
    hasNext: boolean
    hasPrev: boolean
  }
  
  // Actions - Alert CRUD
  loadAlerts: (refresh?: boolean) => Promise<void>
  getAlert: (alertId: string) => Promise<Alert | null>
  createAlert: (data: CreateAlertRequest) => Promise<Alert | null>
  updateAlert: (alertId: string, data: UpdateAlertRequest) => Promise<Alert | null>
  deleteAlert: (alertId: string) => Promise<boolean>
  duplicateAlert: (alertId: string, name?: string) => Promise<Alert | null>
  toggleAlert: (alertId: string, enabled: boolean) => Promise<boolean>
  
  // Actions - Templates
  loadTemplates: (category?: string, search?: string) => Promise<void>
  getTemplate: (templateId: string) => Promise<AlertTemplate | null>
  
  // Actions - Channels
  loadChannels: (teamId?: string) => Promise<void>
  testChannel: (channelId: string) => Promise<boolean>
  
  // Actions - Selection and UI
  selectAlert: (alertId: string) => void
  selectMultipleAlerts: (alertIds: string[]) => void
  clearSelection: () => void
  setFilters: (filters: Partial<AlertFilters>) => void
  setSort: (sort: AlertSortOptions) => void
  setPage: (page: number) => void
  clearError: () => void
  
  // Actions - Bulk operations
  bulkUpdateAlerts: (updates: UpdateAlertRequest) => Promise<boolean>
  bulkDeleteAlerts: () => Promise<boolean>
}

export const useAlertStore = create<AlertStore>()(
  persist(
    (set, get) => ({
      // Initial state
      alerts: [],
      templates: [],
      channels: [],
      selectedAlerts: [],
      currentAlert: null,
      isLoading: false,
      error: null,
      filters: {},
      sort: { field: 'updated_at', direction: 'desc' },
      pagination: {
        page: 1,
        perPage: 20,
        total: 0,
        hasNext: false,
        hasPrev: false,
      },

      // Alert CRUD actions
      loadAlerts: async (refresh = false) => {
        const state = get()
        
        if (state.isLoading && !refresh) return
        
        set({ isLoading: true, error: null })
        
        try {
          const response = await alertApiService.getAlerts(
            state.filters,
            state.sort,
            state.pagination.page,
            state.pagination.perPage
          )
          
          set({
            alerts: response.alerts,
            pagination: {
              page: response.page,
              perPage: response.per_page,
              total: response.total,
              hasNext: response.has_next,
              hasPrev: response.has_prev,
            },
            isLoading: false,
          })
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load alerts',
            isLoading: false,
          })
        }
      },

      getAlert: async (alertId: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const alert = await alertApiService.getAlert(alertId)
          set({ currentAlert: alert, isLoading: false })
          return alert
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load alert',
            isLoading: false,
          })
          return null
        }
      },

      createAlert: async (data: CreateAlertRequest) => {
        set({ isLoading: true, error: null })
        
        try {
          const alert = await alertApiService.createAlert(data)
          
          // Add to alerts list
          set(state => ({
            alerts: [alert, ...state.alerts],
            isLoading: false,
          }))
          
          return alert
        } catch (error: any) {
          set({
            error: error.message || 'Failed to create alert',
            isLoading: false,
          })
          return null
        }
      },

      updateAlert: async (alertId: string, data: UpdateAlertRequest) => {
        set({ isLoading: true, error: null })
        
        try {
          const updatedAlert = await alertApiService.updateAlert(alertId, data)
          
          // Update in alerts list
          set(state => ({
            alerts: state.alerts.map(alert => 
              alert.id === alertId ? updatedAlert : alert
            ),
            currentAlert: state.currentAlert?.id === alertId ? updatedAlert : state.currentAlert,
            isLoading: false,
          }))
          
          return updatedAlert
        } catch (error: any) {
          set({
            error: error.message || 'Failed to update alert',
            isLoading: false,
          })
          return null
        }
      },

      deleteAlert: async (alertId: string) => {
        set({ isLoading: true, error: null })
        
        try {
          await alertApiService.deleteAlert(alertId)
          
          // Remove from alerts list
          set(state => ({
            alerts: state.alerts.filter(alert => alert.id !== alertId),
            selectedAlerts: state.selectedAlerts.filter(id => id !== alertId),
            currentAlert: state.currentAlert?.id === alertId ? null : state.currentAlert,
            isLoading: false,
          }))
          
          return true
        } catch (error: any) {
          set({
            error: error.message || 'Failed to delete alert',
            isLoading: false,
          })
          return false
        }
      },

      duplicateAlert: async (alertId: string, name?: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const duplicatedAlert = await alertApiService.duplicateAlert(alertId, name)
          
          // Add to alerts list
          set(state => ({
            alerts: [duplicatedAlert, ...state.alerts],
            isLoading: false,
          }))
          
          return duplicatedAlert
        } catch (error: any) {
          set({
            error: error.message || 'Failed to duplicate alert',
            isLoading: false,
          })
          return null
        }
      },

      toggleAlert: async (alertId: string, enabled: boolean) => {
        try {
          const updatedAlert = await alertApiService.toggleAlert(alertId, enabled)
          
          // Update in alerts list
          set(state => ({
            alerts: state.alerts.map(alert => 
              alert.id === alertId ? updatedAlert : alert
            ),
            currentAlert: state.currentAlert?.id === alertId ? updatedAlert : state.currentAlert,
          }))
          
          return true
        } catch (error: any) {
          set({ error: error.message || 'Failed to toggle alert' })
          return false
        }
      },

      // Template actions
      loadTemplates: async (category?: string, search?: string) => {
        set({ isLoading: true, error: null })
        
        try {
          const templates = await alertApiService.getTemplates(category, search)
          set({ templates, isLoading: false })
        } catch (error: any) {
          set({
            error: error.message || 'Failed to load templates',
            isLoading: false,
          })
        }
      },

      getTemplate: async (templateId: string) => {
        try {
          return await alertApiService.getTemplate(templateId)
        } catch (error: any) {
          set({ error: error.message || 'Failed to load template' })
          return null
        }
      },

      // Channel actions
      loadChannels: async (teamId?: string) => {
        try {
          const channels = await alertApiService.getNotificationChannels(teamId)
          set({ channels })
        } catch (error: any) {
          set({ error: error.message || 'Failed to load channels' })
        }
      },

      testChannel: async (channelId: string) => {
        try {
          const result = await alertApiService.testNotificationChannel(channelId)
          return result.success
        } catch (error: any) {
          set({ error: error.message || 'Failed to test channel' })
          return false
        }
      },

      // Selection and UI actions
      selectAlert: (alertId: string) => {
        set(state => ({
          selectedAlerts: state.selectedAlerts.includes(alertId)
            ? state.selectedAlerts.filter(id => id !== alertId)
            : [...state.selectedAlerts, alertId]
        }))
      },

      selectMultipleAlerts: (alertIds: string[]) => {
        set({ selectedAlerts: alertIds })
      },

      clearSelection: () => {
        set({ selectedAlerts: [] })
      },

      setFilters: (filters: Partial<AlertFilters>) => {
        set(state => ({
          filters: { ...state.filters, ...filters },
          pagination: { ...state.pagination, page: 1 }, // Reset to first page
        }))
        
        // Reload alerts with new filters
        get().loadAlerts(true)
      },

      setSort: (sort: AlertSortOptions) => {
        set({ sort })
        get().loadAlerts(true)
      },

      setPage: (page: number) => {
        set(state => ({
          pagination: { ...state.pagination, page }
        }))
        get().loadAlerts(true)
      },

      clearError: () => {
        set({ error: null })
      },

      // Bulk operations
      bulkUpdateAlerts: async (updates: UpdateAlertRequest) => {
        const { selectedAlerts } = get()
        
        if (selectedAlerts.length === 0) return false
        
        set({ isLoading: true, error: null })
        
        try {
          await alertApiService.bulkUpdateAlerts(selectedAlerts, updates)
          
          // Reload alerts to get updated data
          await get().loadAlerts(true)
          set({ selectedAlerts: [], isLoading: false })
          
          return true
        } catch (error: any) {
          set({
            error: error.message || 'Failed to update alerts',
            isLoading: false,
          })
          return false
        }
      },

      bulkDeleteAlerts: async () => {
        const { selectedAlerts } = get()
        
        if (selectedAlerts.length === 0) return false
        
        set({ isLoading: true, error: null })
        
        try {
          await alertApiService.bulkDeleteAlerts(selectedAlerts)
          
          // Remove from alerts list
          set(state => ({
            alerts: state.alerts.filter(alert => !selectedAlerts.includes(alert.id)),
            selectedAlerts: [],
            isLoading: false,
          }))
          
          return true
        } catch (error: any) {
          set({
            error: error.message || 'Failed to delete alerts',
            isLoading: false,
          })
          return false
        }
      },
    }),
    {
      name: 'ekko-alert-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        filters: state.filters,
        sort: state.sort,
        pagination: { ...state.pagination, page: 1 }, // Don't persist current page
      }),
    }
  )
)
