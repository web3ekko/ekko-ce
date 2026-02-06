import React, { useState, useEffect } from 'react'
import { Card, Group, Text, Badge, Button, Switch, ActionIcon, Stack, Tooltip, Alert, Progress, Loader } from '@mantine/core'
import { IconWebhook, IconTrash, IconSend, IconCheck, IconX, IconAlertCircle, IconClock, IconActivity } from '@tabler/icons-react'
import type { NotificationChannelEndpoint, WebhookChannelConfig, WebhookHealthMetrics } from '../../services/notifications-api'
import { notificationsApiService } from '../../services/notifications-api'

interface WebhookChannelCardProps {
  channel: NotificationChannelEndpoint
  onToggle: (channelId: string, enabled: boolean) => Promise<void>
  onDelete: (channelId: string) => Promise<void>
  onTest: (channelId: string) => Promise<void>
  stats?: {
    success_count: number
    failure_count: number
    last_success_at?: string
    last_failure_at?: string
  }
}

export function WebhookChannelCard({ channel, onToggle, onDelete, onTest, stats }: WebhookChannelCardProps) {
  const [isToggling, setIsToggling] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [healthMetrics, setHealthMetrics] = useState<WebhookHealthMetrics | null>(null)
  const [isLoadingHealth, setIsLoadingHealth] = useState(false)

  const config = channel.config as WebhookChannelConfig

  // Load health metrics on mount and periodically refresh
  useEffect(() => {
    loadHealthMetrics()

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      loadHealthMetrics()
    }, 30000)

    return () => clearInterval(interval)
  }, [channel.id])

  const loadHealthMetrics = async () => {
    setIsLoadingHealth(true)
    try {
      const health = await notificationsApiService.getWebhookHealth(channel.id)
      setHealthMetrics(health)
    } catch (error) {
      console.error('Failed to load webhook health metrics:', error)
    } finally {
      setIsLoadingHealth(false)
    }
  }

  const handleToggle = async () => {
    setIsToggling(true)
    try {
      await onToggle(channel.id, !channel.enabled)
    } finally {
      setIsToggling(false)
    }
  }

  const handleTest = async () => {
    setIsTesting(true)
    try {
      await onTest(channel.id)
      // Refresh health metrics after test
      setTimeout(() => loadHealthMetrics(), 2000)
    } finally {
      setIsTesting(false)
    }
  }

  const handleDelete = async () => {
    if (window.confirm(`Are you sure you want to delete "${channel.label}"?`)) {
      setIsDeleting(true)
      try {
        await onDelete(channel.id)
      } finally {
        setIsDeleting(false)
      }
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never'
    const date = new Date(dateStr)
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    }).format(date)
  }

  const formatTimestamp = (timestamp?: number) => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp * 1000)
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    }).format(date)
  }

  const getSuccessRate = () => {
    if (!healthMetrics) return 0
    const total = healthMetrics.success_count + healthMetrics.failure_count
    if (total === 0) return 100
    return Math.round((healthMetrics.success_count / total) * 100)
  }

  const getHealthBadgeColor = () => {
    if (!healthMetrics) return 'gray'
    if (!healthMetrics.is_healthy) return 'red'
    if (healthMetrics.consecutive_failures > 0) return 'yellow'
    return 'green'
  }

  const getHealthBadgeText = () => {
    if (!healthMetrics) return 'Unknown'
    if (!healthMetrics.is_healthy) return 'Unhealthy'
    if (healthMetrics.consecutive_failures > 0) return 'Warning'
    return 'Healthy'
  }

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between">
          <Group gap="sm">
            <IconWebhook size={24} color="#7950f2" />
            <div>
              <Text fw={500} size="sm">{channel.label}</Text>
              <Text size="xs" c="dimmed" style={{ maxWidth: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {config.url}
              </Text>
            </div>
          </Group>
          <Group gap="xs">
            <Badge
              color={channel.enabled ? 'green' : 'gray'}
              variant="light"
              leftSection={channel.enabled ? <IconCheck size={12} /> : <IconX size={12} />}
            >
              {channel.enabled ? 'Active' : 'Disabled'}
            </Badge>
            {healthMetrics && (
              <Badge
                color={getHealthBadgeColor()}
                variant="light"
                leftSection={<IconActivity size={12} />}
              >
                {getHealthBadgeText()}
              </Badge>
            )}
          </Group>
        </Group>

        {/* Webhook Config Info */}
        <Stack gap="xs">
          <Group gap="xs">
            <Text size="xs" c="dimmed">Method:</Text>
            <Text size="xs" fw={500}>{config.method || 'POST'}</Text>
          </Group>
          {config.secret && (
            <Group gap="xs">
              <Text size="xs" c="dimmed">HMAC:</Text>
              <Badge size="xs" color="blue" variant="light">Enabled</Badge>
            </Group>
          )}
          <Group gap="xs">
            <Text size="xs" c="dimmed">Created:</Text>
            <Text size="xs">{formatDate(channel.created_at)}</Text>
          </Group>
          {channel.last_used_at && (
            <Group gap="xs">
              <Text size="xs" c="dimmed">Last used:</Text>
              <Text size="xs">{formatDate(channel.last_used_at)}</Text>
            </Group>
          )}
        </Stack>

        {/* Health Metrics */}
        {healthMetrics && (
          <Card withBorder padding="sm" radius="sm" bg="gray.0">
            <Stack gap="sm">
              {/* Success Rate Progress Bar */}
              <div>
                <Group justify="space-between" mb={4}>
                  <Text size="xs" c="dimmed">Success Rate</Text>
                  <Text size="xs" fw={600} c={getSuccessRate() >= 90 ? 'green' : getSuccessRate() >= 70 ? 'yellow' : 'red'}>
                    {getSuccessRate()}%
                  </Text>
                </Group>
                <Progress
                  value={getSuccessRate()}
                  color={getSuccessRate() >= 90 ? 'green' : getSuccessRate() >= 70 ? 'yellow' : 'red'}
                  size="sm"
                  radius="xl"
                />
              </div>

              {/* Delivery Stats */}
              <Group justify="space-around">
                <div style={{ textAlign: 'center' }}>
                  <Text size="xs" c="dimmed">Delivered</Text>
                  <Text size="lg" fw={700} c="green">{healthMetrics.success_count}</Text>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <Text size="xs" c="dimmed">Failed</Text>
                  <Text size="lg" fw={700} c="red">{healthMetrics.failure_count}</Text>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <Group gap={4} justify="center">
                    <IconClock size={14} color="gray" />
                    <Text size="xs" c="dimmed">Avg Response</Text>
                  </Group>
                  <Text size="lg" fw={700} c="blue">{healthMetrics.avg_response_time_ms}ms</Text>
                </div>
              </Group>

              {/* Warning for consecutive failures */}
              {healthMetrics.consecutive_failures > 0 && (
                <Alert icon={<IconAlertCircle size={14} />} color="yellow" variant="light" p="xs">
                  <Text size="xs">
                    {healthMetrics.consecutive_failures} consecutive {healthMetrics.consecutive_failures === 1 ? 'failure' : 'failures'}
                    {healthMetrics.consecutive_failures >= 3 && ' - Endpoint marked unhealthy'}
                  </Text>
                </Alert>
              )}

              {/* Last Error */}
              {healthMetrics.last_error && healthMetrics.failure_count > 0 && (
                <Alert icon={<IconAlertCircle size={14} />} color="red" variant="light" p="xs">
                  <Text size="xs" fw={500}>Last Error:</Text>
                  <Text size="xs" c="dimmed" style={{ wordBreak: 'break-word' }}>
                    {healthMetrics.last_error}
                  </Text>
                  {healthMetrics.last_failure_at && (
                    <Text size="xs" c="dimmed" mt={4}>
                      {formatTimestamp(healthMetrics.last_failure_at)}
                    </Text>
                  )}
                </Alert>
              )}

              {/* Timestamps */}
              <Group justify="space-between">
                {healthMetrics.last_success_at && (
                  <div>
                    <Text size="xs" c="dimmed">Last Success</Text>
                    <Text size="xs">{formatTimestamp(healthMetrics.last_success_at)}</Text>
                  </div>
                )}
              </Group>
            </Stack>
          </Card>
        )}

        {/* Loading Health Metrics */}
        {isLoadingHealth && !healthMetrics && (
          <Card withBorder padding="sm" radius="sm" bg="gray.0">
            <Group justify="center" p="md">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">Loading health metrics...</Text>
            </Group>
          </Card>
        )}

        {/* Delivery Stats (from general stats) */}
        {stats && !healthMetrics && (
          <Card withBorder padding="sm" radius="sm" bg="gray.0">
            <Group justify="space-around">
              <div>
                <Text size="xs" c="dimmed" ta="center">Delivered</Text>
                <Text size="lg" fw={700} c="green" ta="center">{stats.success_count}</Text>
              </div>
              <div>
                <Text size="xs" c="dimmed" ta="center">Failed</Text>
                <Text size="lg" fw={700} c="red" ta="center">{stats.failure_count}</Text>
              </div>
            </Group>
          </Card>
        )}

        {/* Actions */}
        <Group justify="space-between">
          <Switch
            checked={channel.enabled}
            onChange={handleToggle}
            disabled={isToggling}
            label={
              <Text size="xs" c="dimmed">
                {channel.enabled ? 'Enabled' : 'Disabled'}
              </Text>
            }
          />

          <Group gap="xs">
            <Tooltip label="Send test webhook">
              <Button
                variant="light"
                size="xs"
                leftSection={<IconSend size={14} />}
                onClick={handleTest}
                loading={isTesting}
                disabled={!channel.enabled}
              >
                Test
              </Button>
            </Tooltip>

            <Tooltip label="Refresh health metrics">
              <Button
                variant="subtle"
                size="xs"
                leftSection={<IconActivity size={14} />}
                onClick={loadHealthMetrics}
                loading={isLoadingHealth}
              >
                Refresh
              </Button>
            </Tooltip>

            <Tooltip label="Delete webhook">
              <ActionIcon
                variant="light"
                color="red"
                size="lg"
                onClick={handleDelete}
                loading={isDeleting}
              >
                <IconTrash size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </Stack>
    </Card>
  )
}
