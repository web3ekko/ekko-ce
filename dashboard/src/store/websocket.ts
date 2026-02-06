/**
 * WebSocket Store
 *
 * Global state management for WebSocket connection and real-time data
 * Compatible with wasmCloud WebSocket Notification Provider
 */

import { useEffect } from 'react'
import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { websocketService, EVENTS } from '../services/websocket'
import type { ConnectionState } from '../services/websocket'

interface WebSocketStore {
  // Connection state
  connectionState: ConnectionState
  isConnected: boolean
  reconnectAttempts: number

  // Real-time data
  notifications: RealtimeNotification[]
  activeAlerts: number
  systemStatus: SystemStatus

  // Actions
  connect: (token?: string) => void
  disconnect: () => void
  clearNotifications: () => void
  setNotifications: (notifications: RealtimeNotification[]) => void

  // Internal actions
  setConnectionState: (state: ConnectionState) => void
  addNotification: (notification: RealtimeNotification) => void
  updateActiveAlerts: (count: number) => void
  updateSystemStatus: (status: SystemStatus) => void
}

interface RealtimeNotification {
  id: string
  type: 'alert' | 'wallet' | 'team' | 'system'
  title: string
  message: string
  timestamp: string
  severity: 'info' | 'warning' | 'error' | 'success'
  read: boolean
}

interface SystemStatus {
  status: 'operational' | 'degraded' | 'down'
  message?: string
  lastUpdated: string
}

// Track if event listeners have been set up
let eventListenersInitialized = false

export const useWebSocketStore = create<WebSocketStore>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    connectionState: 'disconnected',
    isConnected: false,
    reconnectAttempts: 0,
    notifications: [],
    activeAlerts: 0,
    systemStatus: {
      status: 'operational',
      lastUpdated: new Date().toISOString(),
    },

    // Actions
    connect: (token?: string) => {
      // Prevent multiple connections
      if (get().connectionState === 'connecting' || get().connectionState === 'connected') {
        return
      }

      websocketService.connect(token)

      // Subscribe to connection state changes
      websocketService.onConnectionStateChange((state) => {
        set({
          connectionState: state,
          isConnected: state === 'connected',
        })
      })

      // Set up event listeners only once
      if (!eventListenersInitialized) {
        setupEventListeners()
        eventListenersInitialized = true
      }
    },

    disconnect: () => {
      websocketService.disconnect()
      set({
        connectionState: 'disconnected',
        isConnected: false,
      })
    },

    clearNotifications: () => {
      set({ notifications: [] })
    },

    setNotifications: (notifications: RealtimeNotification[]) => {
      const sorted = [...notifications].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      )
      set({ notifications: sorted.slice(0, 50) })
    },

    // Internal actions
    setConnectionState: (state: ConnectionState) => {
      set({
        connectionState: state,
        isConnected: state === 'connected',
      })
    },

    addNotification: (notification: RealtimeNotification) => {
      set((state) => ({
        notifications: [notification, ...state.notifications].slice(0, 50), // Keep last 50
      }))
    },

    updateActiveAlerts: (count: number) => {
      set({ activeAlerts: count })
    },

    updateSystemStatus: (status: SystemStatus) => {
      set({ systemStatus: status })
    },
  }))
)

// Set up WebSocket event listeners for wasmCloud provider messages
function setupEventListeners() {
  // Alert triggered notifications from wasmCloud provider
  websocketService.on(EVENTS.ALERT_TRIGGERED, (data: Record<string, unknown>) => {
    useWebSocketStore.getState().addNotification({
      id: (data.id as string) || `alert-${Date.now()}`,
      type: 'alert',
      title: (data.alert_name as string) || 'Alert Triggered',
      message: (data.message as string) || 'An alert condition has been met',
      timestamp: (data.timestamp as string) || new Date().toISOString(),
      severity: mapPriorityToSeverity(data.priority as string),
      read: false,
    })
  })

  // Generic notification handler
  websocketService.on('notification', (data: Record<string, unknown>) => {
    useWebSocketStore.getState().addNotification({
      id: (data.id as string) || `notif-${Date.now()}`,
      type: 'alert',
      title: (data.alert_name as string) || 'Notification',
      message: (data.message as string) || '',
      timestamp: (data.timestamp as string) || new Date().toISOString(),
      severity: mapPriorityToSeverity(data.priority as string),
      read: false,
    })
  })

  // System status updates
  websocketService.on(EVENTS.SYSTEM_STATUS, (data: Record<string, unknown>) => {
    useWebSocketStore.getState().updateSystemStatus({
      status: (data.status as 'operational' | 'degraded' | 'down') || 'operational',
      message: data.message as string | undefined,
      lastUpdated: new Date().toISOString(),
    })
  })

  // Dashboard stats updates
  websocketService.on('dashboard:stats', (data: Record<string, unknown>) => {
    if (data.activeAlerts !== undefined) {
      useWebSocketStore.getState().updateActiveAlerts(data.activeAlerts as number)
    }
  })
}

// Map wasmCloud provider priority to UI severity
export function mapPriorityToSeverity(
  priority: string | undefined
): 'info' | 'warning' | 'error' | 'success' {
  switch (priority) {
    case 'critical':
      return 'error'
    case 'high':
      return 'warning'
    case 'normal':
      return 'info'
    case 'low':
      return 'info'
    default:
      return 'warning'
  }
}

// Hook to auto-connect on auth
export function useWebSocketConnection() {
  const connectionState = useWebSocketStore((state) => state.connectionState)
  const connect = useWebSocketStore((state) => state.connect)
  const token = localStorage.getItem('ekko-auth-token')

  // Auto-connect when component mounts
  useEffect(() => {
    if (token && connectionState === 'disconnected') {
      connect(token)
    }
  }, [token, connectionState, connect])

  return { connectionState }
}

// Selectors for specific data
export const selectNotifications = (state: WebSocketStore) => state.notifications
export const selectUnreadNotifications = (state: WebSocketStore) =>
  state.notifications.filter(n => !n.read)
export const selectSystemStatus = (state: WebSocketStore) => state.systemStatus
export const selectConnectionState = (state: WebSocketStore) => ({
  connectionState: state.connectionState,
  isConnected: state.isConnected,
})
