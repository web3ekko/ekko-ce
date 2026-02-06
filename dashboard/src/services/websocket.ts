/**
 * WebSocket Service
 *
 * Native WebSocket connection manager for wasmCloud WebSocket Notification Provider
 * with auto-reconnect, message queuing, and event handling
 */

// Export types at the top of the file
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'
export type SubscriptionCallback<T = unknown> = (data: T) => void

// WebSocket event types
export interface WebSocketEvent<T = unknown> {
  type: string
  data: T
  timestamp: string
}

// Channel names
export const CHANNELS = {
  DASHBOARD: 'dashboard_updates',
  ALERTS: 'alert_events',
  WALLETS: 'wallet_updates',
  TEAM: 'team_activity',
  NFT: 'nft_updates',
  TRANSACTIONS: 'transaction_events',
  SYSTEM: 'system_events',
} as const

export type ChannelName = typeof CHANNELS[keyof typeof CHANNELS]

// Event types for each channel
export const EVENTS = {
  // Alert events
  ALERT_TRIGGERED: 'alert:triggered',
  ALERT_STATUS_CHANGED: 'alert:status',
  ALERT_CREATED: 'alert:created',
  ALERT_UPDATED: 'alert:updated',
  ALERT_DELETED: 'alert:deleted',

  // Wallet events
  WALLET_BALANCE_UPDATED: 'wallet:balance',
  WALLET_TRANSACTION: 'wallet:transaction',
  WALLET_ADDED: 'wallet:added',
  WALLET_REMOVED: 'wallet:removed',

  // Team events
  TEAM_MEMBER_JOINED: 'team:member_joined',
  TEAM_MEMBER_LEFT: 'team:member_left',
  TEAM_ACTIVITY: 'team:activity',
  TEAM_UPDATED: 'team:updated',

  // System events
  SYSTEM_STATUS: 'system:status',
  SYSTEM_MAINTENANCE: 'system:maintenance',
  SYSTEM_NOTIFICATION: 'system:notification',

  // NFT events
  NFT_PRICE_UPDATED: 'nft:price_updated',
  NFT_SALE_DETECTED: 'nft:sale_detected',
  NFT_FLOOR_CHANGED: 'nft:floor_changed',
} as const

export type EventType = typeof EVENTS[keyof typeof EVENTS]

// Message types from wasmCloud WebSocket Provider
// Message types aligned with wasmCloud WebSocket Notification Provider
// Provider uses serde with tag="type" and rename_all="snake_case"
interface AuthMessage {
  type: 'authenticate'  // Provider expects 'authenticate' not 'auth'
  token: string
  device: 'dashboard' | 'ios' | 'android'
}

interface AuthSuccessResponse {
  type: 'authenticated'  // Provider sends 'authenticated' not 'auth_success'
  user_id: string
  connection_id: string
  device: string
}

interface AuthErrorResponse {
  type: 'error'  // Provider sends 'error' not 'auth_error'
  message: string
}

interface NotificationMessage {
  type: 'notification'
  id: string
  alert_id: string
  alert_name: string
  priority: 'low' | 'normal' | 'high' | 'critical'
  message: string
  details?: Record<string, unknown>
  timestamp: string
  actions?: Array<{ label: string; url: string }>
}

interface EventMessage {
  type: 'event'
  event_type?: string
  job_id?: string | null
  payload?: Record<string, unknown> | null
  timestamp?: string
}

interface PingMessage {
  type: 'ping'
  timestamp: number
}

interface PongMessage {
  type: 'pong'
  timestamp: number
}

type IncomingMessage =
  | AuthSuccessResponse
  | AuthErrorResponse
  | NotificationMessage
  | EventMessage
  | PongMessage
  | { type: string; [key: string]: unknown }

class WebSocketService {
  private static instance: WebSocketService
  private socket: WebSocket | null = null
  private connectionState: ConnectionState = 'disconnected'
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private messageQueue: WebSocketEvent[] = []
  private subscriptions: Map<string, Set<SubscriptionCallback>> = new Map()
  private stateListeners: Set<(state: ConnectionState) => void> = new Set()
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null
  private token: string | null = null
  private connectionId: string | null = null
  private userId: string | null = null

  private constructor() { }

  static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService()
    }
    return WebSocketService.instance
  }

  /**
   * Connect to WebSocket server (wasmCloud WebSocket Notification Provider)
   */
  connect(token?: string): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      console.debug('WebSocket already connected')
      return
    }

    if (this.socket?.readyState === WebSocket.CONNECTING) {
      console.debug('WebSocket already connecting')
      return
    }

    this.token = token || null
    this.updateConnectionState('connecting')

    const wsUrl = resolveWebSocketUrl(import.meta.env.VITE_WS_URL)

    try {
      this.socket = new WebSocket(wsUrl)
      this.setupEventHandlers()
    } catch (error) {
      console.debug('WebSocket connection failed:', error)
      this.updateConnectionState('error')
      this.scheduleReconnect()
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.stopHeartbeat()

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect')
      this.socket = null
    }

    this.updateConnectionState('disconnected')
    this.subscriptions.clear()
    this.token = null
    this.connectionId = null
    this.userId = null
    this.reconnectAttempts = 0
  }

  /**
   * Subscribe to specific events
   */
  on<T = unknown>(event: EventType | string, callback: SubscriptionCallback<T>): () => void {
    if (!this.subscriptions.has(event)) {
      this.subscriptions.set(event, new Set())
    }

    const callbacks = this.subscriptions.get(event)!
    callbacks.add(callback as SubscriptionCallback)

    // Return unsubscribe function
    return () => {
      callbacks.delete(callback as SubscriptionCallback)
      if (callbacks.size === 0) {
        this.subscriptions.delete(event)
      }
    }
  }

  /**
   * Send a message to the server
   */
  send<T = unknown>(type: string, data: T): void {
    const message = JSON.stringify({ type, ...data, timestamp: new Date().toISOString() })

    if (this.socket?.readyState !== WebSocket.OPEN) {
      // Queue message if not connected
      this.messageQueue.push({
        type,
        data,
        timestamp: new Date().toISOString(),
      })
      return
    }

    this.socket.send(message)
  }

  /**
   * Subscribe to connection state changes
   */
  onConnectionStateChange(callback: (state: ConnectionState) => void): () => void {
    this.stateListeners.add(callback)

    // Immediately call with current state
    callback(this.connectionState)

    // Return unsubscribe function
    return () => {
      this.stateListeners.delete(callback)
    }
  }

  /**
   * Get current connection state
   */
  getConnectionState(): ConnectionState {
    return this.connectionState
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN
  }

  /**
   * Get connection info
   */
  getConnectionInfo(): { connectionId: string | null; userId: string | null } {
    return {
      connectionId: this.connectionId,
      userId: this.userId,
    }
  }

  private setupEventHandlers(): void {
    if (!this.socket) return

    // Connection opened
    this.socket.onopen = () => {
      console.log('WebSocket connected to wasmCloud provider')
      this.reconnectAttempts = 0

      // Authenticate with Knox token
      if (this.token) {
        this.authenticate(this.token)
      } else {
        // No token, but connection is open
        this.updateConnectionState('connected')
        this.startHeartbeat()
        this.processMessageQueue()
      }
    }

    // Message received
    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const message: IncomingMessage = JSON.parse(event.data)
        this.handleMessage(message)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    // Connection closed
    this.socket.onclose = (event: CloseEvent) => {
      console.debug('WebSocket closed:', event.code, event.reason)
      this.stopHeartbeat()
      this.updateConnectionState('disconnected')

      // Attempt reconnect if not a clean close
      if (event.code !== 1000) {
        this.scheduleReconnect()
      }
    }

    // Connection error
    this.socket.onerror = () => {
      // Note: The error event doesn't contain useful information in browsers
      // The actual error will be followed by a close event
      console.debug('WebSocket connection error (server may be unavailable)')
      this.updateConnectionState('error')
    }
  }

  private authenticate(token: string): void {
    const authMessage: AuthMessage = {
      type: 'authenticate',  // Changed from 'auth' to match provider
      token: token,
      device: 'dashboard',
    }

    this.socket?.send(JSON.stringify(authMessage))
  }

  private handleMessage(message: IncomingMessage): void {
    switch (message.type) {
      case 'authenticated':  // Changed from 'auth_success'
        this.handleAuthSuccess(message as AuthSuccessResponse)
        break

      case 'error':  // Changed from 'auth_error'
        this.handleAuthError(message as AuthErrorResponse)
        break

      case 'notification':
        this.handleNotification(message as NotificationMessage)
        break
      case 'event':
        this.handleEvent(message as EventMessage)
        break

      case 'pong':
        // Heartbeat response received
        break

      default:
        // Dispatch to subscribers
        this.dispatchToSubscribers(message.type, message)
    }
  }

  private handleAuthSuccess(message: AuthSuccessResponse): void {
    console.log('WebSocket authenticated:', message.user_id)
    this.connectionId = message.connection_id
    this.userId = message.user_id
    this.updateConnectionState('connected')
    this.startHeartbeat()
    this.processMessageQueue()
  }

  private handleAuthError(message: AuthErrorResponse): void {
    console.error('WebSocket authentication failed:', message.message)
    this.updateConnectionState('error')
    // Don't auto-reconnect on auth errors - token may be invalid
    this.disconnect()
  }

  private handleNotification(message: NotificationMessage): void {
    // Map notification to appropriate event type
    const eventType = EVENTS.ALERT_TRIGGERED
    this.dispatchToSubscribers(eventType, message)

    // Also dispatch to generic notification handler
    this.dispatchToSubscribers('notification', message)
  }

  private handleEvent(message: EventMessage): void {
    const eventType = typeof message.event_type === 'string' ? message.event_type : null
    const payload = message.payload && typeof message.payload === 'object' ? message.payload : {}
    const enrichedPayload = {
      ...payload,
      job_id: message.job_id ?? (payload as Record<string, unknown>).job_id,
      event_type: message.event_type,
    }

    if (eventType) {
      this.dispatchToSubscribers(eventType, enrichedPayload)
    }

    // Also dispatch a generic event for debugging/metrics subscribers.
    this.dispatchToSubscribers('event', message)
  }

  private dispatchToSubscribers(eventType: string, data: unknown): void {
    const callbacks = this.subscriptions.get(eventType)
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket callback for ${eventType}:`, error)
        }
      })
    }
  }

  private updateConnectionState(state: ConnectionState): void {
    this.connectionState = state
    this.stateListeners.forEach(listener => {
      try {
        listener(state)
      } catch (error) {
        console.error('Error in connection state listener:', error)
      }
    })
  }

  private processMessageQueue(): void {
    if (this.socket?.readyState !== WebSocket.OPEN || this.messageQueue.length === 0) {
      return
    }

    console.log(`Processing ${this.messageQueue.length} queued messages`)

    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift()!
      const payload = JSON.stringify({ type: message.type, ...(message.data as object) })
      this.socket.send(payload)
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()

    // Send ping every 30 seconds (matches wasmCloud provider config)
    this.heartbeatInterval = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        const ping: PingMessage = {
          type: 'ping',
          timestamp: Date.now(),
        }
        this.socket.send(JSON.stringify(ping))
      }
    }, 30000)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
      this.heartbeatInterval = null
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnection attempts reached')
      return
    }

    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelay
    )

    this.reconnectAttempts++
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`)

    setTimeout(() => {
      if (this.connectionState !== 'connected') {
        this.connect(this.token || undefined)
      }
    }, delay)
  }
}

export function resolveWebSocketUrl(envUrl?: string, locationOverride?: Location): string {
  const location = locationOverride || window.location
  const rawEnv = envUrl?.trim() || ''
  let wsUrl = rawEnv

  if (!wsUrl) {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const port = location.port ? `:${location.port}` : ''
    const host = location.hostname.startsWith('dashboard.')
      ? location.hostname.replace('dashboard.', 'api.')
      : location.hostname
    wsUrl = `${protocol}://${host}${port}`
  }

  if (location.protocol === 'https:' && wsUrl.startsWith('ws://')) {
    wsUrl = wsUrl.replace(/^ws:\/\//, 'wss://')
  }

  wsUrl = wsUrl.replace(/\/$/, '')
  if (!wsUrl.endsWith('/ws')) {
    wsUrl = `${wsUrl}/ws`
  }

  return wsUrl
}

// Export singleton instance
export const websocketService = WebSocketService.getInstance()

// Export types
export type { WebSocketService }
