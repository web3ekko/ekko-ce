/**
 * WebSocket Provider Component
 * 
 * Provides WebSocket connection management and real-time updates
 * throughout the application
 */

import { useEffect, ReactNode } from 'react'
import { notifications } from '@mantine/notifications'
import { IconWifi, IconWifiOff, IconAlertCircle } from '@tabler/icons-react'
import { useWebSocketStore } from '../store/websocket'
import { useAuthStore } from '../store/auth'

interface WebSocketProviderProps {
  children: ReactNode
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const connect = useWebSocketStore((state) => state.connect)
  const disconnect = useWebSocketStore((state) => state.disconnect)
  const connectionState = useWebSocketStore((state) => state.connectionState)
  const { isAuthenticated, tokens } = useAuthStore()

  useEffect(() => {
    // Connect when authenticated
    if (isAuthenticated && tokens?.access) {
      connect(tokens.access)
    } else {
      disconnect()
    }

    // Cleanup on unmount
    return () => {
      // We don't disconnect here to maintain connection across route changes
      // disconnect()
    }
  }, [isAuthenticated, tokens?.access, connect, disconnect])

  // Show connection status notifications (only for successful connections)
  // Note: Error/disconnected states are handled gracefully without alarming users
  // since the WebSocket server may not be available in all environments
  useEffect(() => {
    if (connectionState === 'connected') {
      notifications.show({
        id: 'ws-connected',
        title: 'Connected',
        message: 'Real-time updates are active',
        color: 'green',
        icon: <IconWifi size={20} />,
        autoClose: 3000,
      })
    }
    // Don't show error/disconnected notifications - graceful degradation
    // The ConnectionIndicator component shows the status visually
  }, [connectionState])

  return <>{children}</>
}

// Connection status indicator component
export function ConnectionIndicator() {
  const connectionState = useWebSocketStore((state) => state.connectionState)

  const getStatusColor = (): 'green' | 'yellow' | 'red' | 'gray' => {
    switch (connectionState) {
      case 'connected':
        return 'green'
      case 'connecting':
        return 'yellow'
      case 'error':
        return 'red'
      default:
        return 'gray'
    }
  }

  const getStatusLabel = () => {
    switch (connectionState) {
      case 'connected':
        return 'Live'
      case 'connecting':
        return 'Connecting...'
      case 'error':
        return 'Offline'
      default:
        return 'Offline'
    }
  }

  const color = getStatusColor()

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 8px',
        borderRadius: '4px',
        backgroundColor: color === 'green' ? 'rgba(34, 197, 94, 0.1)' :
                        color === 'yellow' ? 'rgba(234, 179, 8, 0.1)' :
                        'rgba(156, 163, 175, 0.1)',
      }}
      title={`Connection: ${connectionState}`}
    >
      <div
        style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          backgroundColor: color === 'green' ? '#22c55e' :
                          color === 'yellow' ? '#eab308' :
                          color === 'red' ? '#ef4444' : '#9ca3af',
          animation: connectionState === 'connecting' ? 'pulse 2s infinite' : undefined
        }}
      />
      {connectionState === 'connected' ? (
        <IconWifi size={14} color="#22c55e" />
      ) : (
        <IconWifiOff size={14} color="#9ca3af" />
      )}
      <span style={{
        fontSize: '12px',
        fontWeight: 500,
        color: color === 'green' ? '#22c55e' :
               color === 'yellow' ? '#eab308' : '#9ca3af'
      }}>
        {getStatusLabel()}
      </span>
    </div>
  )
}