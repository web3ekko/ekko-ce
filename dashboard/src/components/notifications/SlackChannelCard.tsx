import React, { useState } from 'react'
import { Card, Group, Text, Badge, Button, Switch, ActionIcon, Stack, Tooltip } from '@mantine/core'
import { IconBrandSlack, IconTrash, IconSend, IconCheck, IconX } from '@tabler/icons-react'
import type { NotificationChannelEndpoint, SlackChannelConfig } from '../../services/notifications-api'

interface SlackChannelCardProps {
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

export function SlackChannelCard({ channel, onToggle, onDelete, onTest, stats }: SlackChannelCardProps) {
  const [isToggling, setIsToggling] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const config = channel.config as SlackChannelConfig

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

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between">
          <Group gap="sm">
            <IconBrandSlack size={24} color="#4A154B" />
            <div>
              <Text fw={500} size="sm">{channel.label}</Text>
              <Text size="xs" c="dimmed">{config.workspace_name || 'Slack Workspace'}</Text>
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
            {channel.verified && (
              <Badge color="blue" variant="light">
                Verified
              </Badge>
            )}
          </Group>
        </Group>

        {/* Channel Info */}
        <Stack gap="xs">
          <Group gap="xs">
            <Text size="xs" c="dimmed">Channel:</Text>
            <Text size="xs" fw={500}>{config.channel || '#alerts'}</Text>
          </Group>
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

        {/* Delivery Stats */}
        {stats && (
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
            <Tooltip label="Send test message">
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

            <Tooltip label="Delete channel">
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
