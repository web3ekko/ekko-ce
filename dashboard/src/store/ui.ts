/**
 * UI Store
 * 
 * Global state management for UI preferences and behavior
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIStore {
  // Sidebar
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
  
  // Mobile
  mobileNavOpen: boolean
  setMobileNavOpen: (open: boolean) => void
  
  // Modals
  modals: {
    createAlert: boolean
    walletDetails: boolean
    teamInvite: boolean
    settings: boolean
  }
  openModal: (modal: keyof UIStore['modals']) => void
  closeModal: (modal: keyof UIStore['modals']) => void
  closeAllModals: () => void
  
  // Notifications
  notificationPosition: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left'
  setNotificationPosition: (position: UIStore['notificationPosition']) => void
  
  // Table preferences
  tablePageSize: number
  setTablePageSize: (size: number) => void
  
  // Dashboard layout
  dashboardLayout: 'grid' | 'list' | 'compact'
  setDashboardLayout: (layout: 'grid' | 'list' | 'compact') => void
  
  // Feature flags
  featureFlags: {
    naturalLanguageAlerts: boolean
    advancedCharts: boolean
    aiAssistant: boolean
  }
  setFeatureFlag: (flag: keyof UIStore['featureFlags'], enabled: boolean) => void
  
  // Loading states
  globalLoading: boolean
  setGlobalLoading: (loading: boolean) => void
  
  // Toast/notification queue
  toastQueue: Array<{
    id: string
    type: 'success' | 'error' | 'warning' | 'info'
    title: string
    message?: string
    duration?: number
  }>
  addToast: (toast: Omit<UIStore['toastQueue'][0], 'id'>) => void
  removeToast: (id: string) => void
  
  // User preferences
  preferences: {
    compactMode: boolean
    showAnimations: boolean
    soundEnabled: boolean
    autoRefresh: boolean
    refreshInterval: number // in seconds
  }
  setPreference: <K extends keyof UIStore['preferences']>(
    key: K,
    value: UIStore['preferences'][K]
  ) => void
  
  // Reset
  resetUIStore: () => void
}

const initialState = {
  sidebarCollapsed: false,
  mobileNavOpen: false,
  modals: {
    createAlert: false,
    walletDetails: false,
    teamInvite: false,
    settings: false,
  },
  notificationPosition: 'top-right' as const,
  tablePageSize: 10,
  dashboardLayout: 'grid' as const,
  featureFlags: {
    naturalLanguageAlerts: true,
    advancedCharts: true,
    aiAssistant: true,
  },
  globalLoading: false,
  toastQueue: [],
  preferences: {
    compactMode: false,
    showAnimations: true,
    soundEnabled: true,
    autoRefresh: true,
    refreshInterval: 30,
  },
}

export const useUIStore = create<UIStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      // Sidebar actions
      toggleSidebar: () => set((state) => ({ 
        sidebarCollapsed: !state.sidebarCollapsed 
      })),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      
      // Mobile nav actions
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
      
      // Modal actions
      openModal: (modal) => set((state) => ({
        modals: { ...state.modals, [modal]: true }
      })),
      closeModal: (modal) => set((state) => ({
        modals: { ...state.modals, [modal]: false }
      })),
      closeAllModals: () => set({ modals: initialState.modals }),
      
      // Notification actions
      setNotificationPosition: (position) => set({ notificationPosition: position }),
      
      // Table actions
      setTablePageSize: (size) => set({ tablePageSize: size }),
      
      // Dashboard layout actions
      setDashboardLayout: (layout) => set({ dashboardLayout: layout }),
      
      // Feature flag actions
      setFeatureFlag: (flag, enabled) => set((state) => ({
        featureFlags: { ...state.featureFlags, [flag]: enabled }
      })),
      
      // Loading actions
      setGlobalLoading: (loading) => set({ globalLoading: loading }),
      
      // Toast actions
      addToast: (toast) => set((state) => ({
        toastQueue: [...state.toastQueue, { ...toast, id: Date.now().toString() }]
      })),
      removeToast: (id) => set((state) => ({
        toastQueue: state.toastQueue.filter((t) => t.id !== id)
      })),
      
      // Preference actions
      setPreference: (key, value) => set((state) => ({
        preferences: { ...state.preferences, [key]: value }
      })),
      
      // Reset action
      resetUIStore: () => set(initialState),
    }),
    {
      name: 'ui-storage',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        notificationPosition: state.notificationPosition,
        tablePageSize: state.tablePageSize,
        dashboardLayout: state.dashboardLayout,
        featureFlags: state.featureFlags,
        preferences: state.preferences,
      }),
    }
  )
)

// Selectors
export const selectSidebarCollapsed = (state: UIStore) => state.sidebarCollapsed
export const selectMobileNavOpen = (state: UIStore) => state.mobileNavOpen
export const selectModals = (state: UIStore) => state.modals
export const selectFeatureFlags = (state: UIStore) => state.featureFlags
export const selectPreferences = (state: UIStore) => state.preferences
export const selectDashboardLayout = (state: UIStore) => state.dashboardLayout