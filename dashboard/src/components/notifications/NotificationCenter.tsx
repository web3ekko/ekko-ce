/**
 * Notification Center Component
 * 
 * Displays notification history and manages notification preferences
 */

import { useEffect, useState } from 'react'
import {
  Popover,
  Badge,
  ActionIcon,
  Stack,
  Text,
  Group,
  Button,
  ScrollArea,
  Divider,
  Paper,
  ThemeIcon,
  Tooltip,
  Center,
} from '@mantine/core'
import {
  IconBell,
  IconBellOff,
  IconVolume,
  IconVolumeOff,
  IconTrash,
  IconCheck,
  IconAlertCircle,
  IconAlertTriangle,
  IconInfoCircle,
} from '@tabler/icons-react'
import { mapPriorityToSeverity, useWebSocketStore } from '../../store/websocket'
import { notificationService } from '../../services/notifications'
import { notificationsApiService } from '../../services/notifications-api'
import { motion, AnimatePresence } from 'framer-motion'

const iconMap = {
  info: IconInfoCircle,
  warning: IconAlertTriangle,
  error: IconAlertCircle,
  success: IconCheck,
  critical: IconBell,
}

const colorMap = {
  info: 'blue',
  warning: 'yellow',
  error: 'red',
  success: 'green',
  critical: 'red',
}

export function NotificationCenter() {
  const [opened, setOpened] = useState(false)
  const [soundEnabled, setSoundEnabled] = useState(notificationService.isSoundEnabled())
  // Use selectors to prevent re-renders
  const notifications = useWebSocketStore((state) => state.notifications)
  const clearNotifications = useWebSocketStore((state) => state.clearNotifications)
  const setNotifications = useWebSocketStore((state) => state.setNotifications)
  
  // Calculate derived state locally to avoid selector issues
  const unreadNotifications = notifications.filter(n => !n.read)
  const unreadCount = unreadNotifications.length

  useEffect(() => {
    if (!opened || notifications.length > 0) {
      return
    }

    let cancelled = false

    const loadHistory = async () => {
      try {
        const history = await notificationsApiService.getHistory({ limit: 50 })
        if (cancelled) return

        const mapped = history.results.map((item) => ({
          id: item.notification_id || `history-${item.alert_id}`,
          type: 'alert' as const,
          title: item.title || item.alert_name || 'Notification',
          message: item.message || item.title || item.alert_name || '',
          timestamp: item.created_at,
          severity: mapPriorityToSeverity(item.priority),
          read: true,
        }))

        if (mapped.length > 0) {
          setNotifications(mapped)
        }
      } catch (error) {
        console.error('Failed to load notification history:', error)
      }
    }

    loadHistory()

    return () => {
      cancelled = true
    }
  }, [opened, notifications.length, setNotifications])

  const truncateAddress = (address: string, chars: number = 4) => {
    if (!address || address.length < chars * 2 + 2) return address
    return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`
  }

  const formatNotificationText = (text: string) => {
    if (!text) return text
    return text.replace(/0x[a-fA-F0-9]{40}/g, (match) => truncateAddress(match, 4))
  }


  const handleToggleSound = () => {
    const newState = notificationService.toggleSound()
    setSoundEnabled(newState)
  }

  const markAsRead = (id: string) => {
    // In a real app, this would update the store
    console.log('Mark as read:', id)
  }

  const getRelativeTime = (timestamp: string) => {
    if (!timestamp) return '—'
    const now = Date.now()
    const time = new Date(timestamp).getTime()
    if (Number.isNaN(time)) return '—'
    const diff = now - time

    if (diff < 60 * 1000) return 'Just now'
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}m ago`
    if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))}h ago`
    return new Date(timestamp).toLocaleDateString()
  }

  return (
    <Popover 
      opened={opened} 
      onChange={setOpened}
      width={400}
      position="bottom-end"
      withArrow
      shadow="lg"
      radius="md"
    >
      <Popover.Target>
        <Tooltip label="Notifications">
          <ActionIcon 
            size="lg" 
            variant="subtle"
            onClick={() => setOpened((o) => !o)}
            aria-label="Notifications"
            data-testid="notification-center-button"
          >
            <div style={{ position: 'relative' }}>
              <IconBell size={20} />
              <AnimatePresence>
                {unreadCount > 0 && (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    exit={{ scale: 0 }}
                    style={{
                      position: 'absolute',
                      top: -8,
                      right: -8,
                    }}
                  >
                    <Badge
                      size="xs"
                      color="red"
                      circle
                      styles={{
                        root: {
                          padding: 0,
                          minWidth: 18,
                          height: 18,
                        },
                      }}
                    >
                      {unreadCount}
                    </Badge>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </ActionIcon>
        </Tooltip>
      </Popover.Target>

      <Popover.Dropdown p={0}>
        <Stack spacing={0}>
          {/* Header */}
          <Group position="apart" px="md" py="sm">
            <Text size="sm" weight={600}>
              Notifications
            </Text>
            <Group spacing="xs">
              <Tooltip label={soundEnabled ? 'Disable sound' : 'Enable sound'}>
                <ActionIcon
                  size="sm"
                  variant="subtle"
                  onClick={handleToggleSound}
                  color={soundEnabled ? 'blue' : 'gray'}
                >
                  {soundEnabled ? <IconVolume size={16} /> : <IconVolumeOff size={16} />}
                </ActionIcon>
              </Tooltip>
              {notifications.length > 0 && (
                <Tooltip label="Clear all">
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    onClick={clearNotifications}
                    color="red"
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Tooltip>
              )}
            </Group>
          </Group>

          <Divider />

          {/* Notifications List */}
          {notifications.length > 0 ? (
            <ScrollArea.Autosize maxHeight={400} px="md" py="xs" data-testid="notification-center-list">
              <Stack spacing="xs">
                <AnimatePresence>
                  {notifications.map((notification) => {
                    const Icon = iconMap[notification.severity]
                    const color = colorMap[notification.severity]
                    const rawTitle = (notification.title || '').trim()
                    const rawMessage = (notification.message || '').trim()
                    const displayTitle =
                      formatNotificationText(rawTitle || rawMessage || 'Notification')
                    const displayMessage = formatNotificationText(rawMessage || rawTitle)

                    return (
                      <motion.div
                        key={notification.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                      >
                        <Paper
                          p="sm"
                          radius="sm"
                          withBorder
                          style={{
                            borderLeft: `3px solid var(--mantine-color-${color}-6)`,
                            cursor: notification.read ? 'default' : 'pointer',
                            backgroundColor: notification.read 
                              ? 'transparent' 
                              : `var(--mantine-color-${color}-0)`,
                          }}
                          onClick={() => !notification.read && markAsRead(notification.id)}
                        >
                          <Group noWrap align="flex-start">
                            <ThemeIcon
                              size="sm"
                              radius="xl"
                              color={color}
                              variant="light"
                            >
                              <Icon size={14} />
                            </ThemeIcon>
                            <Stack spacing={4} style={{ flex: 1 }}>
                              <Group position="apart" align="flex-start" wrap="nowrap">
                                <Text
                                  size="sm"
                                  fw={600}
                                  c="#0F172A"
                                  style={{
                                    flex: 1,
                                    minWidth: 0,
                                    whiteSpace: 'normal',
                                    wordBreak: 'break-word',
                                    overflowWrap: 'anywhere',
                                  }}
                                >
                                  {displayTitle}
                                </Text>
                                <Text size="xs" c="#64748B">
                                  {getRelativeTime(notification.timestamp)}
                                </Text>
                              </Group>
                              {displayMessage && (
                                <Text
                                  size="sm"
                                  c="#475569"
                                  style={{
                                    whiteSpace: 'normal',
                                    wordBreak: 'break-word',
                                    overflowWrap: 'anywhere',
                                  }}
                                >
                                  {displayMessage}
                                </Text>
                              )}
                            </Stack>
                          </Group>
                        </Paper>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              </Stack>
            </ScrollArea.Autosize>
          ) : (
            <Center py="xl">
              <Stack align="center" spacing="xs">
                <IconBellOff size={32} color="gray" />
                <Text size="sm" color="dimmed">
                  No notifications
                </Text>
              </Stack>
            </Center>
          )}

          {/* Footer */}
          <Divider />
          <Group position="center" p="xs">
            <Button 
              variant="subtle" 
              size="xs"
              onClick={() => {
                setOpened(false)
                // Navigate to full notifications page
              }}
            >
              View all notifications
            </Button>
          </Group>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}
