/**
 * DefaultNetworkAlertCard Component
 *
 * Card displaying a default network alert (system-wide fallback alert per chain/subnet).
 * Users can toggle these alerts on/off to control default notifications.
 */

import {
  Card,
  Text,
  Group,
  Badge,
  Stack,
  Switch,
  ThemeIcon,
} from '@mantine/core'
import { IconBell, IconNetwork } from '@tabler/icons-react'
import type { DefaultNetworkAlert } from '../../services/groups-api'
import { ChainLogo } from '../brand/ChainLogo'
import { getChainColor } from '../../utils/chain-identity'

interface DefaultNetworkAlertCardProps {
  alert: DefaultNetworkAlert
  onToggle: (id: string, enabled: boolean) => Promise<void>
}

export function DefaultNetworkAlertCard({ alert, onToggle }: DefaultNetworkAlertCardProps) {
  const chainColor = getChainColor(alert.chain)

  const handleToggle = async (checked: boolean) => {
    await onToggle(alert.id, checked)
  }

  return (
    <Card
      padding="md"
      radius="md"
      style={{
        background: '#FFFFFF',
        border: '1px solid #E6E9EE',
        borderLeft: `4px solid ${chainColor}`,
      }}
    >
      <Group justify="space-between">
        <Group gap="sm">
          <ThemeIcon
            size="lg"
            radius="md"
            variant="light"
            style={{ backgroundColor: `${chainColor}15`, color: chainColor }}
          >
            <IconNetwork size={20} />
          </ThemeIcon>
          <ChainLogo chain={alert.chain} size="sm" />
          <Stack gap={2}>
            <Group gap="xs">
              <Text fw={600} c="#0F172A">{alert.chain_name}</Text>
              <Badge size="xs" variant="light" color="gray">
                {alert.subnet}
              </Badge>
            </Group>
            <Group gap="xs">
              <IconBell size={12} color="#64748B" />
              <Text size="xs" c="#64748B">
                {alert.alert_template_name || 'All Transactions Alert'}
              </Text>
            </Group>
          </Stack>
        </Group>

        <Group gap="md">
          <Badge
            size="sm"
            variant="light"
            color="gray"
            style={{ fontWeight: 500 }}
          >
            System Default
          </Badge>
          <Switch
            checked={alert.enabled}
            onChange={(e) => handleToggle(e.currentTarget.checked)}
            color="teal"
            size="md"
            styles={{
              track: {
                cursor: 'pointer',
              },
            }}
          />
        </Group>
      </Group>
    </Card>
  )
}
