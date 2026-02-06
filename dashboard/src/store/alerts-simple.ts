/**
 * Simple Alert Store
 * 
 * Basic alert state management without complex dependencies
 */

import { create } from 'zustand'

// Simple alert type for development
interface SimpleAlert {
  id: string
  name: string
  description: string
  status: 'active' | 'paused' | 'error' | 'draft'
  event_type: string
  created_at: string
  enabled: boolean
  trigger_count: number
  last_triggered?: string
}

interface SimpleAlertStore {
  // State
  alerts: SimpleAlert[]
  selectedAlerts: string[]
  isLoading: boolean
  error: string | null
  
  // Actions
  loadAlerts: () => Promise<void>
  createAlert: (alert: Omit<SimpleAlert, 'id' | 'created_at' | 'trigger_count'>) => void
  updateAlert: (id: string, updates: Partial<SimpleAlert>) => void
  deleteAlert: (id: string) => void
  toggleAlert: (id: string) => void
  selectAlert: (id: string) => void
  clearSelection: () => void
  setError: (error: string | null) => void
}

// Alerts are created via UI - no mock data

export const useSimpleAlertStore = create<SimpleAlertStore>((set, get) => ({
  // Initial state
  alerts: [],
  selectedAlerts: [],
  isLoading: false,
  error: null,

  // Load alerts - no mock data, users create via UI
  loadAlerts: async () => {
    set({ isLoading: true, error: null })

    try {
      // No mock data - alerts are created via UI
      await new Promise(resolve => setTimeout(resolve, 100))

      set({ isLoading: false })
    } catch {
      set({
        error: 'Failed to load alerts',
        isLoading: false
      })
    }
  },

  // Create new alert
  createAlert: (alertData) => {
    const newAlert: SimpleAlert = {
      ...alertData,
      id: Date.now().toString(),
      created_at: new Date().toISOString(),
      trigger_count: 0,
    }
    
    set(state => ({
      alerts: [newAlert, ...state.alerts]
    }))
  },

  // Update existing alert
  updateAlert: (id, updates) => {
    set(state => ({
      alerts: state.alerts.map(alert =>
        alert.id === id ? { ...alert, ...updates } : alert
      )
    }))
  },

  // Delete alert
  deleteAlert: (id) => {
    set(state => ({
      alerts: state.alerts.filter(alert => alert.id !== id),
      selectedAlerts: state.selectedAlerts.filter(selectedId => selectedId !== id)
    }))
  },

  // Toggle alert enabled/disabled
  toggleAlert: (id) => {
    set(state => ({
      alerts: state.alerts.map(alert =>
        alert.id === id 
          ? { 
              ...alert, 
              enabled: !alert.enabled,
              status: !alert.enabled ? 'active' : 'paused'
            } 
          : alert
      )
    }))
  },

  // Select/deselect alert
  selectAlert: (id) => {
    set(state => ({
      selectedAlerts: state.selectedAlerts.includes(id)
        ? state.selectedAlerts.filter(selectedId => selectedId !== id)
        : [...state.selectedAlerts, id]
    }))
  },

  // Clear all selections
  clearSelection: () => {
    set({ selectedAlerts: [] })
  },

  // Set error message
  setError: (error) => {
    set({ error })
  },
}))
