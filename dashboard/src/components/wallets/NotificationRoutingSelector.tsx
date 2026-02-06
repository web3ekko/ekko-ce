/**
 * NotificationRoutingSelector Component
 *
 * Allows users to configure how notifications are delivered for provider-managed wallet groups.
 * Options: callback_only, user_channels, or both.
 */

import { Radio, Stack, Text, Group, Badge, ThemeIcon } from '@mantine/core'
import { IconWebhook, IconBell, IconArrowsLeftRight } from '@tabler/icons-react'
import type { NotificationRoutingChoice } from '../../services/groups-api'

interface NotificationRoutingSelectorProps {
  value: NotificationRoutingChoice
  onChange: (value: NotificationRoutingChoice) => void
  callbackUrl?: string
  disabled?: boolean
}

export function NotificationRoutingSelector({
  value,
  onChange,
  callbackUrl,
  disabled = false,
}: NotificationRoutingSelectorProps) {
  return (
    <Radio.Group
      label="Notification Delivery"
      description="Choose how you want to receive alerts for this wallet group"
      value={value}
      onChange={(val) => onChange(val as NotificationRoutingChoice)}
    >
      <Stack gap="sm" mt="xs">
        <Radio
          value="callback_only"
          disabled={disabled}
          label={
            <Group gap="xs">
              <ThemeIcon size="sm" variant="light" color="teal">
                <IconWebhook size={14} />
              </ThemeIcon>
              <Text size="sm" fw={500}>Provider Webhook Only</Text>
            </Group>
          }
          description={
            callbackUrl ? (
              <Text size="xs" c="dimmed">
                Sends to: <Badge size="xs" variant="light">{callbackUrl}</Badge>
              </Text>
            ) : (
              <Text size="xs" c="dimmed">Provider receives all notifications via webhook</Text>
            )
          }
          styles={{
            body: { alignItems: 'flex-start' },
            description: { marginTop: 4 },
          }}
        />

        <Radio
          value="user_channels"
          disabled={disabled}
          label={
            <Group gap="xs">
              <ThemeIcon size="sm" variant="light" color="blue">
                <IconBell size={14} />
              </ThemeIcon>
              <Text size="sm" fw={500}>My Notification Channels Only</Text>
            </Group>
          }
          description={
            <Text size="xs" c="dimmed">
              Uses your configured Slack, Telegram, email, etc.
            </Text>
          }
          styles={{
            body: { alignItems: 'flex-start' },
            description: { marginTop: 4 },
          }}
        />

        <Radio
          value="both"
          disabled={disabled}
          label={
            <Group gap="xs">
              <ThemeIcon size="sm" variant="light" color="teal">
                <IconArrowsLeftRight size={14} />
              </ThemeIcon>
              <Text size="sm" fw={500}>Both</Text>
            </Group>
          }
          description={
            <Text size="xs" c="dimmed">
              Sends to provider webhook AND your notification channels
            </Text>
          }
          styles={{
            body: { alignItems: 'flex-start' },
            description: { marginTop: 4 },
          }}
        />
      </Stack>
    </Radio.Group>
  )
}
