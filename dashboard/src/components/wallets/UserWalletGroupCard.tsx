/**
 * UserWalletGroupCard Component
 *
 * Card displaying a provider-managed wallet group with notification routing configuration.
 */

import { useEffect, useState } from 'react'
import {
  Card,
  Text,
  Group,
  Badge,
  Stack,
  ActionIcon,
  Collapse,
  Button,
  Switch,
  TextInput,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconChevronDown,
  IconChevronUp,
  IconWallet,
  IconWebhook,
  IconShieldCheck,
  IconTrash,
  IconX,
  IconPlus,
  IconDatabaseImport,
} from '@tabler/icons-react'
import { NotificationRoutingSelector } from './NotificationRoutingSelector'
import WalletLogo from '../brand/WalletLogo'
import ChainLogo from '../brand/ChainLogo'
import type {
  UserWalletGroup,
  NotificationRoutingChoice,
  UpdateUserWalletGroupRequest,
} from '../../services/groups-api'

interface UserWalletGroupCardProps {
  group: UserWalletGroup
  onUpdate: (groupId: string, updates: UpdateUserWalletGroupRequest) => Promise<void>
  onDisconnect?: (groupId: string) => Promise<void>
  onAddWallets?: (groupId: string, walletKeys: string[]) => Promise<void>
  onRemoveWallet?: (groupId: string, walletKey: string) => Promise<void>
  onBulkImport?: (groupId: string) => void
}

export function UserWalletGroupCard({
  group,
  onUpdate,
  onDisconnect,
  onAddWallets,
  onRemoveWallet,
  onBulkImport,
}: UserWalletGroupCardProps) {
  const [expanded, { toggle }] = useDisclosure(false)
  const [routing, setRouting] = useState<NotificationRoutingChoice>(group.notification_routing)
  const [autoSubscribe, setAutoSubscribe] = useState<boolean>(group.auto_subscribe_alerts)
  const [isActive, setIsActive] = useState<boolean>(group.is_active)
  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [newWalletKey, setNewWalletKey] = useState('')
  const [isWalletSaving, setIsWalletSaving] = useState(false)

  useEffect(() => {
    setRouting(group.notification_routing)
    setAutoSubscribe(group.auto_subscribe_alerts)
    setIsActive(group.is_active)
    setHasChanges(false)
  }, [group.notification_routing, group.auto_subscribe_alerts, group.is_active])

  const recomputeHasChanges = (next: { routing: NotificationRoutingChoice; autoSubscribe: boolean; isActive: boolean }) => {
    setHasChanges(
      next.routing !== group.notification_routing ||
        next.autoSubscribe !== group.auto_subscribe_alerts ||
        next.isActive !== group.is_active
    )
  }

  const handleRoutingChange = (newRouting: NotificationRoutingChoice) => {
    setRouting(newRouting)
    recomputeHasChanges({ routing: newRouting, autoSubscribe, isActive })
  }

  const handleAutoSubscribeChange = (value: boolean) => {
    setAutoSubscribe(value)
    recomputeHasChanges({ routing, autoSubscribe: value, isActive })
  }

  const handleActiveChange = (value: boolean) => {
    setIsActive(value)
    recomputeHasChanges({ routing, autoSubscribe, isActive: value })
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onUpdate(group.id, {
        notification_routing: routing,
        auto_subscribe_alerts: autoSubscribe,
        is_active: isActive,
      })
      setHasChanges(false)
    } catch {
      // Notifications are handled by the caller; keep local changes for retry.
    } finally {
      setIsSaving(false)
    }
  }

  // Extract callback URL from config
  const callbackUrl = group.callback?.config?.url
  const canManageWallets = Boolean(onAddWallets || onRemoveWallet || onBulkImport)

  const handleAddWallet = async () => {
    if (!onAddWallets) return
    const trimmed = newWalletKey.trim()
    if (!trimmed) return
    setIsWalletSaving(true)
    try {
      await onAddWallets(group.id, [trimmed])
      setNewWalletKey('')
    } finally {
      setIsWalletSaving(false)
    }
  }

  const handleRemoveWallet = async (walletKey: string) => {
    if (!onRemoveWallet) return
    if (!confirm(`Remove ${walletKey} from "${group.wallet_group_name}"?`)) return
    setIsWalletSaving(true)
    try {
      await onRemoveWallet(group.id, walletKey)
    } finally {
      setIsWalletSaving(false)
    }
  }

  return (
    <Card
      padding="md"
      radius="md"
      style={{
        background: '#FFFFFF',
        border: '1px solid #E6E9EE',
        borderLeft: '4px solid #14B8A6', // teal for provider-managed
      }}
    >
      <Group justify="space-between" mb={expanded ? 'md' : 0}>
        <Group gap="sm">
          <WalletLogo name={group.provider_name} size="sm" label={group.provider_name} />
          <Stack gap={2}>
            <Group gap="xs">
              <Text fw={600} c="#0F172A">{group.wallet_group_name}</Text>
              <Badge size="xs" color="teal" variant="light">
                Provider Managed
              </Badge>
              {!group.is_active && (
                <Badge size="xs" color="gray" variant="light">
                  Paused
                </Badge>
              )}
            </Group>
            <Text size="xs" c="#64748B">
              {group.wallet_keys.length} wallets managed by {group.provider_name}
            </Text>
          </Stack>
        </Group>

        <Group gap="xs">
          {group.callback && (
            <Badge
              size="sm"
              variant="light"
              color="teal"
              leftSection={<IconWebhook size={12} />}
            >
              Webhook
            </Badge>
          )}
          {group.auto_subscribe_alerts && (
            <Badge
              size="sm"
              variant="light"
              color="blue"
              leftSection={<IconShieldCheck size={12} />}
            >
              Auto-alerts
            </Badge>
          )}
          {onDisconnect && (
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label="Disconnect provider wallet group"
              onClick={async () => {
                if (!confirm(`Disconnect from "${group.wallet_group_name}"?`)) return
                try {
                  await onDisconnect(group.id)
                } catch {
                  // Notifications are handled by the caller.
                }
              }}
            >
              <IconTrash size={18} />
            </ActionIcon>
          )}
          <ActionIcon variant="subtle" aria-label="Toggle provider wallet group details" onClick={toggle}>
            {expanded ? <IconChevronUp size={18} /> : <IconChevronDown size={18} />}
          </ActionIcon>
        </Group>
      </Group>

      <Collapse in={expanded}>
        <Stack gap="md" mt="md">
          {/* Wallet Keys Preview */}
          <div>
            <Group justify="space-between" mb="xs">
              <Text size="xs" fw={500} c="#475569">
                Wallets in this group:
              </Text>
              {onBulkImport && (
                <Button
                  size="xs"
                  variant="subtle"
                  leftSection={<IconDatabaseImport size={14} />}
                  onClick={() => onBulkImport(group.id)}
                >
                  Bulk import
                </Button>
              )}
            </Group>
            <Group gap={4}>
              {group.wallet_keys.slice(0, 5).map((key) => {
                const parts = key.split(':')
                const chain = parts[0] || 'Unknown'
                const address = parts[2] || key
                const shortAddress = address.length > 12
                  ? `${address.slice(0, 6)}...${address.slice(-4)}`
                  : address

                return (
                  <Badge
                    key={key}
                    size="xs"
                    variant="outline"
                    color="gray"
                    leftSection={<ChainLogo chain={chain} size="xs" />}
                    rightSection={onRemoveWallet ? (
                      <ActionIcon
                        size="xs"
                        variant="transparent"
                        aria-label="Remove wallet from provider group"
                        onClick={() => void handleRemoveWallet(key)}
                      >
                        <IconX size={10} />
                      </ActionIcon>
                    ) : undefined}
                  >
                    {chain}: {shortAddress}
                  </Badge>
                )
              })}
              {group.wallet_keys.length > 5 && (
                <Badge size="xs" variant="light" color="gray">
                  +{group.wallet_keys.length - 5} more
                </Badge>
              )}
            </Group>
            {group.wallet_keys.length === 0 && (
              <Text size="xs" c="#94A3B8" mt="xs">
                No wallets added yet.
              </Text>
            )}
            {onAddWallets && (
              <Group mt="sm" align="flex-end">
                <TextInput
                  label="Add wallet key"
                  placeholder="ETH:mainnet:0x..."
                  value={newWalletKey}
                  onChange={(e) => setNewWalletKey(e.currentTarget.value)}
                  style={{ flex: 1 }}
                />
                <Button
                  size="xs"
                  leftSection={<IconPlus size={14} />}
                  onClick={() => void handleAddWallet()}
                  loading={isWalletSaving}
                  disabled={!newWalletKey.trim()}
                >
                  Add
                </Button>
              </Group>
            )}
            {!canManageWallets && (
              <Text size="xs" c="#94A3B8" mt="xs">
                Wallet membership is managed by your provider.
              </Text>
            )}
          </div>

          {/* Notification Routing Selector */}
          <NotificationRoutingSelector
            value={routing}
            onChange={handleRoutingChange}
            callbackUrl={callbackUrl}
          />

          <Group grow>
            <Switch
              label="Active"
              checked={isActive}
              onChange={(e) => handleActiveChange(e.currentTarget.checked)}
            />
            <Switch
              label="Auto-subscribe alerts"
              checked={autoSubscribe}
              onChange={(e) => handleAutoSubscribeChange(e.currentTarget.checked)}
            />
          </Group>

          {/* Save button - only show if changes made */}
          {hasChanges && (
            <Group justify="flex-end">
              <Button
                size="xs"
                variant="subtle"
                onClick={() => {
                  setRouting(group.notification_routing)
                  setAutoSubscribe(group.auto_subscribe_alerts)
                  setIsActive(group.is_active)
                  setHasChanges(false)
                }}
              >
                Cancel
              </Button>
              <Button
                size="xs"
                onClick={handleSave}
                loading={isSaving}
                style={{ backgroundColor: '#2563EB' }}
              >
                Save Changes
              </Button>
            </Group>
          )}
        </Stack>
      </Collapse>
    </Card>
  )
}
