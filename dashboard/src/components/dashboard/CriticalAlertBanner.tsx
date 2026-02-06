/**
 * Critical Alert Banner Component
 *
 * Surface the most recent high-severity real-time notifications.
 */

import { useMemo, useState } from 'react'
import {
  Text,
  Group,
  Button,
  Collapse,
  Stack,
  Badge,
  ActionIcon,
  Box,
  ThemeIcon,
} from '@mantine/core'
import {
  IconAlertTriangle,
  IconChevronDown,
  IconChevronUp,
  IconCheck,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { useWebSocketStore } from '../../store/websocket'

interface CriticalAlert {
  id: string
  title: string
  message: string
  severity: 'critical' | 'high' | 'medium'
  timestamp: string
}

const mapSeverity = (severity: 'info' | 'warning' | 'error' | 'success'): CriticalAlert['severity'] => {
  if (severity === 'error') return 'critical'
  if (severity === 'warning') return 'high'
  return 'medium'
}

export function CriticalAlertBanner() {
  const notifications = useWebSocketStore((state) => state.notifications)
  const [expanded, setExpanded] = useState(false)
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())

  const criticalAlerts = useMemo(() => {
    return notifications
      .filter((notification) =>
        !notification.read &&
        !dismissedIds.has(notification.id) &&
        (notification.severity === 'error' || notification.severity === 'warning')
      )
      .map((notification) => ({
        id: notification.id,
        title: notification.title,
        message: notification.message,
        severity: mapSeverity(notification.severity),
        timestamp: notification.timestamp,
      }))
  }, [dismissedIds, notifications])

  if (criticalAlerts.length === 0) return null

  const mostRecentAlert = criticalAlerts[0]

  const handleAcknowledge = (alertId: string) => {
    setDismissedIds((prev) => new Set([...prev, alertId]))
  }

  const getSeverityColor = (severity: CriticalAlert['severity']) => {
    switch (severity) {
      case 'critical':
        return 'red'
      case 'high':
        return 'orange'
      case 'medium':
        return 'yellow'
      default:
        return 'gray'
    }
  }

  const formatRelativeTime = (timestamp: string) => {
    const diffMins = Math.floor((Date.now() - new Date(timestamp).getTime()) / 60000)
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    return `${Math.floor(diffMins / 60)}h ago`
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
      >
        <ExecutiveCard
          variant="solid"
          p={0}
          style={{
            borderLeft: `4px solid var(--mantine-color-${getSeverityColor(mostRecentAlert.severity)}-6)`,
            backgroundColor: `var(--mantine-color-${getSeverityColor(mostRecentAlert.severity)}-0)`,
          }}
        >
          <Stack gap={0}>
            <Group justify="space-between" p="md" wrap="nowrap">
              <Group gap="md">
                <ThemeIcon
                  size="lg"
                  radius="md"
                  color={getSeverityColor(mostRecentAlert.severity)}
                  variant="light"
                >
                  <IconAlertTriangle size={20} />
                </ThemeIcon>

                <Box>
                  <Group gap="xs">
                    <Text fw={700} size="sm" c="dark.9">
                      {mostRecentAlert.title}
                    </Text>
                    <Badge
                      size="xs"
                      variant="dot"
                      color={getSeverityColor(mostRecentAlert.severity)}
                    >
                      {mostRecentAlert.severity.toUpperCase()}
                    </Badge>
                  </Group>
                  <Group gap="xs" align="center">
                    <Text size="xs" c="dimmed">
                      {formatRelativeTime(mostRecentAlert.timestamp)}
                    </Text>
                  </Group>
                </Box>
              </Group>

              <Group gap="xs">
                <Button
                  size="xs"
                  variant="light"
                  color="gray"
                  onClick={() => handleAcknowledge(mostRecentAlert.id)}
                  leftSection={<IconCheck size={14} />}
                >
                  Dismiss
                </Button>

                {criticalAlerts.length > 1 && (
                  <ActionIcon
                    variant="subtle"
                    color="gray"
                    onClick={() => setExpanded(!expanded)}
                  >
                    {expanded ? <IconChevronUp size={18} /> : <IconChevronDown size={18} />}
                  </ActionIcon>
                )}
              </Group>
            </Group>

            <Collapse in={expanded}>
              <Box p="md" pt={0}>
                <Stack gap="sm">
                  <Text size="sm" c="dimmed">
                    {mostRecentAlert.message}
                  </Text>

                  {criticalAlerts.length > 1 && (
                    <Box pt="sm" style={{ borderTop: '1px solid var(--mantine-color-gray-3)' }}>
                      <Text size="xs" fw={600} mb="xs" c="dimmed">
                        OTHER ACTIVE ALERTS ({criticalAlerts.length - 1})
                      </Text>
                      <Stack gap="xs">
                        {criticalAlerts.slice(1).map((alert) => (
                          <Group key={alert.id} justify="space-between">
                            <Group gap="xs">
                              <Badge size="xs" color={getSeverityColor(alert.severity)} variant="outline" />
                              <Text size="xs">{alert.title}</Text>
                            </Group>
                            <Button
                              size="xs"
                              variant="subtle"
                              color="gray"
                              onClick={() => handleAcknowledge(alert.id)}
                            >
                              Dismiss
                            </Button>
                          </Group>
                        ))}
                      </Stack>
                    </Box>
                  )}
                </Stack>
              </Box>
            </Collapse>
          </Stack>
        </ExecutiveCard>
      </motion.div>
    </AnimatePresence>
  )
}
