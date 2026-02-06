/**
 * Provider Wallets Page
 *
 * Lists provider-managed wallet groups (UserWalletGroup) and lets the user control
 * notification routing and other user-editable settings.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconAlertCircle,
  IconArrowLeft,
  IconCheck,
  IconShieldCheck,
  IconPlus,
} from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import notificationsApiService, { type NotificationChannelEndpoint } from '../../services/notifications-api'
import groupsApiService, {
  type CreateUserWalletGroupRequest,
  type GenericGroup,
  type NotificationRoutingChoice,
  type UpdateUserWalletGroupRequest,
  type UserWalletGroup,
  type UserWalletGroupImportResponse,
} from '../../services/groups-api'
import { UserWalletGroupCard } from '../../components/wallets/UserWalletGroupCard'
import { NotificationRoutingSelector } from '../../components/wallets/NotificationRoutingSelector'

export function ProviderWalletsPage() {
  const navigate = useNavigate()

  const [groups, setGroups] = useState<UserWalletGroup[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [walletGroups, setWalletGroups] = useState<GenericGroup[]>([])
  const [webhooks, setWebhooks] = useState<NotificationChannelEndpoint[]>([])
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false)
  const [importOpened, { open: openImport, close: closeImport }] = useDisclosure(false)
  const [importTargetId, setImportTargetId] = useState<string | null>(null)
  const [importFormat, setImportFormat] = useState<'csv' | 'json'>('csv')
  const [importPayload, setImportPayload] = useState('')
  const [importMergeMode, setImportMergeMode] = useState<'append' | 'replace'>('append')
  const [importDedupe, setImportDedupe] = useState(true)

  const [formWalletGroup, setFormWalletGroup] = useState<string | null>(null)
  const [formCallback, setFormCallback] = useState<string | null>(null)
  const [formWalletKeys, setFormWalletKeys] = useState('')
  const [formRouting, setFormRouting] = useState<NotificationRoutingChoice>('callback_only')
  const [formAutoSubscribe, setFormAutoSubscribe] = useState(true)
  const [formIsActive, setFormIsActive] = useState(true)

  const load = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await groupsApiService.getUserWalletGroups()
      setGroups(response.results || [])
    } catch (err) {
      console.error('Failed to load provider wallets:', err)
      setError(err instanceof Error ? err.message : 'Failed to load provider wallets')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (!createOpened) return

    const loadOptions = async () => {
      try {
        const [walletsResp, webhooksResp] = await Promise.all([
          groupsApiService.getWalletGroups({ page_size: 200 }),
          notificationsApiService.getChannels({ channel_type: 'webhook', page_size: 200 }),
        ])
        setWalletGroups(walletsResp.results || [])
        setWebhooks(webhooksResp.results || [])
      } catch (err) {
        notifications.show({
          title: 'Error',
          message: err instanceof Error ? err.message : 'Failed to load provider options',
          color: 'red',
          icon: <IconAlertCircle size={16} />,
        })
      }
    }

    void loadOptions()
  }, [createOpened])

  const resetCreateForm = () => {
    setFormWalletGroup(null)
    setFormCallback(null)
    setFormWalletKeys('')
    setFormRouting('callback_only')
    setFormAutoSubscribe(true)
    setFormIsActive(true)
  }

  const handleUpdate = async (groupId: string, updates: UpdateUserWalletGroupRequest) => {
    try {
      const updated = await groupsApiService.updateUserWalletGroup(groupId, updates)
      setGroups((prev) => prev.map((g) => (g.id === groupId ? updated : g)))
      notifications.show({
        title: 'Saved',
        message: 'Provider wallet settings updated',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to update settings',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      throw err
    }
  }

  const handleDisconnect = async (groupId: string) => {
    try {
      await groupsApiService.deleteUserWalletGroup(groupId)
      setGroups((prev) => prev.filter((g) => g.id !== groupId))
      notifications.show({
        title: 'Disconnected',
        message: 'Provider wallet group removed',
        color: 'orange',
      })
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to disconnect',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      throw err
    }
  }

  const refreshGroup = async (groupId: string) => {
    const updated = await groupsApiService.getUserWalletGroup(groupId)
    setGroups((prev) => prev.map((g) => (g.id === groupId ? updated : g)))
  }

  const handleAddWallets = async (groupId: string, walletKeys: string[]) => {
    try {
      await groupsApiService.addUserWalletGroupWallets(groupId, { wallet_keys: walletKeys, dedupe: true })
      await refreshGroup(groupId)
      notifications.show({
        title: 'Wallet added',
        message: 'Wallet added to provider group',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to add wallet',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      throw err
    }
  }

  const handleRemoveWallet = async (groupId: string, walletKey: string) => {
    try {
      await groupsApiService.removeUserWalletGroupWallets(groupId, { wallet_keys: [walletKey] })
      await refreshGroup(groupId)
      notifications.show({
        title: 'Wallet removed',
        message: 'Wallet removed from provider group',
        color: 'orange',
      })
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to remove wallet',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
      throw err
    }
  }

  const handleImport = async () => {
    if (!importTargetId) return
    setIsSaving(true)
    try {
      const response: UserWalletGroupImportResponse = await groupsApiService.importUserWalletGroupWallets(
        importTargetId,
        {
          format: importFormat,
          payload: importPayload,
          merge_mode: importMergeMode,
          dedupe: importDedupe,
        }
      )
      await refreshGroup(importTargetId)
      notifications.show({
        title: 'Import complete',
        message: `Added ${response.added.length} wallets (${response.invalid_rows.length} invalid)`,
        color: response.invalid_rows.length ? 'yellow' : 'green',
      })
      closeImport()
      setImportPayload('')
      setImportTargetId(null)
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to import wallets',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleCreate = async () => {
    if (!formWalletGroup) {
      notifications.show({
        title: 'Missing wallet group',
        message: 'Select a wallet group to create a provider membership.',
        color: 'red',
      })
      return
    }

    setIsSaving(true)
    const walletKeys = formWalletKeys
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean)

    const payload: CreateUserWalletGroupRequest = {
      wallet_group: formWalletGroup,
      wallet_keys: walletKeys.length ? walletKeys : undefined,
      callback: formCallback || null,
      notification_routing: formRouting,
      auto_subscribe_alerts: formAutoSubscribe,
      is_active: formIsActive,
    }

    try {
      const created = await groupsApiService.createUserWalletGroup(payload)
      setGroups((prev) => [created, ...prev])
      notifications.show({
        title: 'Created',
        message: 'Provider wallet group created',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      closeCreate()
      resetCreateForm()
    } catch (err) {
      notifications.show({
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to create provider wallet group',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const selectedCallbackUrl = webhooks.find((hook) => hook.id === formCallback)?.config?.url as
    | string
    | undefined

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Button
          variant="subtle"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => navigate('/dashboard/wallets')}
          w="fit-content"
        >
          Back to Wallets
        </Button>

        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap="sm" mb={4}>
              <IconShieldCheck size={20} />
              <Title order={2}>Provider Wallets</Title>
            </Group>
            <Text c="dimmed" size="sm" maw={760}>
              Wallets managed by a provider (e.g., exchange, wallet app). These do not appear in your Accounts.
              You control how notifications are delivered for each provider group.
            </Text>
          </div>
          <Button variant="light" onClick={() => void load()} disabled={isLoading}>
            Refresh
          </Button>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => {
              resetCreateForm()
              openCreate()
            }}
          >
            Create Provider Group
          </Button>
        </Group>

        {error && (
          <Alert color="red" icon={<IconAlertCircle size={16} />}>
            {error}
          </Alert>
        )}

        {isLoading ? (
          <Center h={240}>
            <Stack align="center" gap="sm">
              <Loader color="blue" />
              <Text c="dimmed">Loading provider wallets…</Text>
            </Stack>
          </Center>
        ) : groups.length === 0 ? (
          <Card withBorder padding="xl" radius="md">
            <Stack gap="sm" align="center">
              <Text fw={600}>No provider-managed wallets</Text>
              <Text c="dimmed" size="sm" ta="center" maw={520}>
                When a provider connects wallets on your behalf, they will appear here with routing controls.
              </Text>
              <Button
                leftSection={<IconPlus size={16} />}
                onClick={() => {
                  resetCreateForm()
                  openCreate()
                }}
              >
                Create Provider Group
              </Button>
            </Stack>
          </Card>
        ) : (
          <Stack gap="md">
            {groups.map((group) => (
              <UserWalletGroupCard
                key={group.id}
                group={group}
                onUpdate={handleUpdate}
                onDisconnect={handleDisconnect}
                onAddWallets={handleAddWallets}
                onRemoveWallet={handleRemoveWallet}
                onBulkImport={(groupId) => {
                  setImportTargetId(groupId)
                  openImport()
                }}
              />
            ))}
          </Stack>
        )}
      </Stack>

      <Modal
        opened={createOpened}
        onClose={() => {
          closeCreate()
          resetCreateForm()
        }}
        title="Create Provider Wallet Group"
        size="lg"
      >
        <Stack>
          <Select
            label="Wallet Group"
            placeholder="Select a wallet group"
            data={walletGroups.map((group) => ({ value: group.id, label: group.name }))}
            value={formWalletGroup}
            onChange={setFormWalletGroup}
            searchable
            required
          />
          <Select
            label="Provider Webhook (optional)"
            placeholder={webhooks.length ? 'Select a webhook' : 'No webhook channels found'}
            data={webhooks.map((hook) => ({ value: hook.id, label: hook.label }))}
            value={formCallback}
            onChange={setFormCallback}
            searchable
            clearable
          />
          <NotificationRoutingSelector
            value={formRouting}
            onChange={setFormRouting}
            callbackUrl={selectedCallbackUrl}
          />
          <Textarea
            label="Initial Wallet Keys (optional)"
            description="One wallet key per line: NETWORK:subnet:address"
            minRows={3}
            value={formWalletKeys}
            onChange={(e) => setFormWalletKeys(e.currentTarget.value)}
          />
          <Group grow>
            <Switch
              label="Auto-subscribe alerts"
              checked={formAutoSubscribe}
              onChange={(e) => setFormAutoSubscribe(e.currentTarget.checked)}
            />
            <Switch
              label="Active"
              checked={formIsActive}
              onChange={(e) => setFormIsActive(e.currentTarget.checked)}
            />
          </Group>
          <Group justify="flex-end">
            <Button
              variant="subtle"
              onClick={() => {
                closeCreate()
                resetCreateForm()
              }}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void handleCreate()}
              loading={isSaving}
              disabled={!formWalletGroup}
              style={{ backgroundColor: '#2563EB' }}
            >
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={importOpened}
        onClose={() => {
          closeImport()
          setImportPayload('')
          setImportTargetId(null)
        }}
        title="Bulk Import Wallets"
        size="lg"
      >
        <Stack>
          <Group grow>
            <Select
              label="Format"
              data={[
                { value: 'csv', label: 'CSV' },
                { value: 'json', label: 'JSON' },
              ]}
              value={importFormat}
              onChange={(value) => setImportFormat(value === 'json' ? 'json' : 'csv')}
            />
            <Select
              label="Merge Mode"
              data={[
                { value: 'append', label: 'Append' },
                { value: 'replace', label: 'Replace' },
              ]}
              value={importMergeMode}
              onChange={(value) => setImportMergeMode(value === 'replace' ? 'replace' : 'append')}
            />
          </Group>
          <Textarea
            label="Payload"
            placeholder={
              importFormat === 'csv'
                ? 'network,subnet,address\nETH,mainnet,0xabc...\nSOL,mainnet,5yBb...'
                : '[{"network":"ETH","subnet":"mainnet","address":"0xabc..."}]'
            }
            minRows={6}
            value={importPayload}
            onChange={(e) => setImportPayload(e.currentTarget.value)}
          />
          <Switch
            label="Dedupe wallet keys"
            checked={importDedupe}
            onChange={(e) => setImportDedupe(e.currentTarget.checked)}
          />
          <Group justify="flex-end">
            <Button
              variant="subtle"
              onClick={() => {
                closeImport()
                setImportPayload('')
                setImportTargetId(null)
              }}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void handleImport()}
              loading={isSaving}
              disabled={!importPayload.trim()}
              style={{ backgroundColor: '#2563EB' }}
            >
              Import
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
