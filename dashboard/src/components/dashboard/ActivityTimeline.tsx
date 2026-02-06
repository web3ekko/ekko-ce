/**
 * Activity Timeline Component
 *
 * Real-time feed of system events, transactions, and alerts
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Text,
  Group,
  Stack,
  ThemeIcon,
  Badge,
  ActionIcon,
  ScrollArea,
  Box,
  Loader,
  Center,
  Button,
} from '@mantine/core'
import {
  IconArrowsExchange,
  IconAlertTriangle,
  IconShieldCheck,
  IconLogin,
  IconSettings,
  IconRefresh,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { dashboardApiService, type ActivityItem } from '../../services/dashboard-api'

interface ActivityEvent {
  id: string
  type: 'transaction' | 'alert' | 'security' | 'system' | 'execution' | 'alert_created' | 'group_joined'
  title: string
  description: string
  timestamp: string
  severity?: 'critical' | 'high' | 'medium' | 'low'
  metadata?: Record<string, any>
}

// Map API activity items to display events
function mapActivityToEvent(item: ActivityItem): ActivityEvent {
  let type: ActivityEvent['type'] = 'system'
  if (item.type === 'execution') type = 'alert'
  else if (item.type === 'alert_created') type = 'alert'
  else if (item.type === 'group_joined') type = 'system'

  return {
    id: item.id,
    type,
    title: item.title,
    description: item.subtitle,
    timestamp: item.timestamp,
    severity: item.metadata?.triggered ? 'medium' : undefined,
    metadata: item.metadata,
  }
}

export function ActivityTimeline() {
  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isAutoScroll, setIsAutoScroll] = useState(true)

  // Fetch activity from API
  const fetchActivity = useCallback(async () => {
    try {
      const response = await dashboardApiService.getActivity({ limit: 50 })
      const mappedEvents = response.activities.map(mapActivityToEvent)
      setEvents(mappedEvents)
    } catch (error) {
      console.error('Failed to fetch activity:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Initial fetch
  useEffect(() => {
    fetchActivity()
  }, [fetchActivity])

  // Refresh activity periodically
  useEffect(() => {
    if (!isAutoScroll) return

    const interval = setInterval(() => {
      fetchActivity()
    }, 30000) // Refresh every 30 seconds

    return () => clearInterval(interval)
  }, [isAutoScroll, fetchActivity])

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'transaction': return <IconArrowsExchange size={16} />
      case 'alert': return <IconAlertTriangle size={16} />
      case 'security': return <IconShieldCheck size={16} />
      case 'system': return <IconSettings size={16} />
      default: return <IconLogin size={16} />
    }
  }

  const getEventColor = (type: string, severity?: string) => {
    if (severity === 'critical') return 'red'
    if (severity === 'high') return 'orange'

    switch (type) {
      case 'transaction': return 'blue'
      case 'alert': return 'yellow'
      case 'security': return 'teal'
      case 'system': return 'gray'
      default: return 'blue'
    }
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <ExecutiveCard
      size="compact"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' } as React.CSSProperties}
    >
      <Group justify="space-between" mb="xs">
        <Text fw={600} size="sm">Activity</Text>
        <ActionIcon
          variant="subtle"
          size="xs"
          color={isAutoScroll ? 'blue' : 'gray'}
          onClick={() => setIsAutoScroll(!isAutoScroll)}
          title={isAutoScroll ? "Auto-scroll enabled" : "Auto-scroll disabled"}
        >
          <IconRefresh size={12} style={{ animation: isAutoScroll ? 'spin 4s linear infinite' : 'none' }} />
        </ActionIcon>
      </Group>

      <ScrollArea h={280} offsetScrollbars type="always">
        {isLoading ? (
          <Center h={200}>
            <Loader size="sm" />
          </Center>
        ) : events.length === 0 ? (
          <Center h={200}>
            <Stack align="center" gap="xs">
              <Box p="md" style={{ background: '#F1F5F9', borderRadius: '50%' }}>
                <IconArrowsExchange size={24} color="#64748B" />
              </Box>
              <Text size="sm" fw={500} c="#0F172A">No activity detected</Text>
              <Text size="xs" c="dimmed" ta="center" maw={200}>
                Connect a wallet to see real-time transactions and alerts.
              </Text>
              <Button size="xs" variant="light" mt="xs">
                Connect Wallet
              </Button>
            </Stack>
          </Center>
        ) : (
          <Stack gap={6}>
            <AnimatePresence initial={false}>
              {events.map((event) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <Box
                    p={6}
                    style={{
                      backgroundColor: 'var(--mantine-color-gray-0)',
                      borderRadius: 'var(--mantine-radius-sm)',
                      border: '1px solid var(--mantine-color-gray-2)',
                    }}
                  >
                    <Group align="center" wrap="nowrap" gap={6}>
                      <ThemeIcon
                        variant="light"
                        size="xs"
                        radius="sm"
                        color={getEventColor(event.type, event.severity)}
                      >
                        {getEventIcon(event.type)}
                      </ThemeIcon>

                      <Box style={{ flex: 1, minWidth: 0 }}>
                        <Group justify="space-between" gap={4}>
                          <Text size="xs" fw={600} c="dark.9" lineClamp={1}>
                            {event.title}
                          </Text>
                          <Group gap={4}>
                            {event.severity && (
                              <Badge
                                size="xs"
                                variant="dot"
                                color={getEventColor(event.type, event.severity)}
                              >
                                {event.severity}
                              </Badge>
                            )}
                            <Text size="xs" c="dimmed">
                              {formatTime(event.timestamp)}
                            </Text>
                          </Group>
                        </Group>
                      </Box>
                    </Group>
                  </Box>
                </motion.div>
              ))}
            </AnimatePresence>
          </Stack>
        )}
      </ScrollArea>
    </ExecutiveCard>
  )
}