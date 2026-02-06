/**
 * Wallet Group Detail Page
 *
 * Shows members + settings for a wallet group.
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconArrowLeft, IconCheck, IconCopy, IconPlus, IconTrash } from '@tabler/icons-react'
import groupsApiService from '../../services/groups-api'
import type { GenericGroup } from '../../services/groups-api'
import { useWalletStore } from '../../store/wallets'
import { usePersonalizationStore } from '../../store/personalization'
import { parseWalletKey, truncateMiddle } from '../../utils/wallet-display'

function isSystemAccountsGroup(group: GenericGroup): boolean {
  const settings = group.settings as { system_key?: string } | undefined
  return settings?.system_key === 'accounts'
}

export function WalletGroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { accounts, loadAccounts, deleteWalletGroup } = useWalletStore()
  const loadChains = usePersonalizationStore((s) => s.loadChains)
  const loadWalletNicknames = usePersonalizationStore((s) => s.loadWalletNicknames)
  const getChainId = usePersonalizationStore((s) => s.getChainId)
  const getWalletNickname = usePersonalizationStore((s) => s.getWalletNickname)

  const [group, setGroup] = useState<GenericGroup | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [addOpened, { open: openAdd, close: closeAdd }] = useDisclosure(false)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    void loadAccounts()
    void loadWalletNicknames()
    void loadChains()
  }, [loadAccounts, loadWalletNicknames, loadChains])

  const loadGroup = async () => {
    if (!id) return
    setIsLoading(true)
    setError(null)
    try {
      const full = await groupsApiService.getGroup(id)
      setGroup(full)
    } catch (error) {
      console.error('Failed to load group:', error)
      setError('Failed to load group')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadGroup()
  }, [id])

  const members = useMemo(() => {
    const membersMap = group?.member_data?.members || {}
    return Object.entries(membersMap).map(([memberKey, meta]) => ({
      memberKey,
      meta,
    }))
  }, [group])

  const accountLabelByKey = useMemo(() => {
    const map = new Map<string, string>()
    accounts.forEach((a) => {
      if (a.label) map.set(a.wallet_key, a.label)
    })
    return map
  }, [accounts])

  const selectableAccountOptions = useMemo(() => {
    const existing = new Set(group?.member_keys || [])
    return accounts
      .filter((a) => !existing.has(a.wallet_key))
      .map((a) => ({
        value: a.wallet_key,
        label: `${a.label || getWalletNickname(a.address, getChainId(a.network)) || truncateMiddle(a.address)} · ${a.network}:${a.subnet}`,
      }))
  }, [accounts, group, getWalletNickname, getChainId])

  const handleCopy = async (value: string) => {
    await navigator.clipboard.writeText(value)
    notifications.show({
      title: 'Copied',
      message: 'Copied to clipboard',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
  }

  const handleRemoveMember = async (memberKey: string) => {
    if (!group) return
    if (!confirm('Remove this member from the group?')) return
    setIsSaving(true)
    try {
      await groupsApiService.removeMembers(group.id, { members: [{ member_key: memberKey }] })
      await loadGroup()
    } finally {
      setIsSaving(false)
    }
  }

  const handleAddMembers = async () => {
    if (!group) return
    if (!selectedKeys.length) return
    setIsSaving(true)
    try {
      await groupsApiService.addMembers(group.id, {
        members: selectedKeys.map((walletKey) => ({
          member_key: walletKey,
          label: accountLabelByKey.get(walletKey) || '',
        })),
      })
      notifications.show({
        title: 'Members Added',
        message: `${selectedKeys.length} wallet(s) added`,
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      setSelectedKeys([])
      closeAdd()
      await loadGroup()
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to add members',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteGroup = async () => {
    if (!group || isSystemAccountsGroup(group)) return
    if (!confirm(`Delete "${group.name}"?`)) return
    setIsSaving(true)
    try {
      await deleteWalletGroup(group.id)
      navigate('/dashboard/wallets/groups')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Loader size="lg" color="blue" />
          <Text c="dimmed">Loading group…</Text>
        </Stack>
      </Center>
    )
  }

  if (!group) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Text c="dimmed">{error || 'Group not found'}</Text>
          <Button variant="light" onClick={() => navigate('/dashboard/wallets/groups')}>
            Back to groups
          </Button>
        </Stack>
      </Center>
    )
  }

  const visibility = (group.settings as { visibility?: string } | undefined)?.visibility || 'private'

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Button
          variant="subtle"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => navigate('/dashboard/wallets/groups')}
          w="fit-content"
        >
          Back to Groups
        </Button>

        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap="sm" mb={4}>
              <Title order={2}>{group.name}</Title>
              <Badge variant="light" color={visibility === 'public' ? 'blue' : 'gray'}>
                {visibility}
              </Badge>
              <Badge variant="light" color="gray">
                {members.length} members
              </Badge>
            </Group>
            {group.description && <Text c="dimmed">{group.description}</Text>}
            {isSystemAccountsGroup(group) && (
              <Text size="sm" c="dimmed" mt="xs">
                This is your Accounts group. It is private and system-managed.
              </Text>
            )}
          </div>
          <Group>
            <Button leftSection={<IconPlus size={16} />} onClick={openAdd} disabled={isSaving}>
              Add members
            </Button>
            {!isSystemAccountsGroup(group) && (
              <Button variant="light" color="red" leftSection={<IconTrash size={16} />} onClick={() => void handleDeleteGroup()} disabled={isSaving}>
                Delete
              </Button>
            )}
          </Group>
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red">
            {error}
          </Alert>
        )}

        <Card withBorder padding="md" radius="md">
          <Title order={4} mb="md">Members</Title>
          {members.length === 0 ? (
            <Text c="dimmed">No members in this group yet.</Text>
          ) : (
            <Table verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Label</Table.Th>
                  <Table.Th>Key</Table.Th>
                  <Table.Th>Added</Table.Th>
                  <Table.Th style={{ width: 140 }} />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {members.map(({ memberKey, meta }) => {
                  const parsed = parseWalletKey(memberKey)
                  const nickname = getWalletNickname(parsed.address, getChainId(parsed.network))
                  const label = meta.label || accountLabelByKey.get(memberKey) || nickname || truncateMiddle(parsed.address || memberKey)
                  return (
                    <Table.Tr key={memberKey}>
                      <Table.Td>
                        <Text fw={600} size="sm">{label}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" style={{ fontFamily: 'monospace' }}>
                          {truncateMiddle(memberKey, 10, 10)}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" c="dimmed">
                          {meta.added_at ? new Date(meta.added_at).toLocaleString() : '—'}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Group justify="flex-end" gap={6}>
                          <Tooltip label="Copy">
                            <ActionIcon variant="subtle" onClick={() => void handleCopy(memberKey)}>
                              <IconCopy size={16} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="Remove">
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              onClick={() => void handleRemoveMember(memberKey)}
                              disabled={isSystemAccountsGroup(group) || isSaving}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  )
                })}
              </Table.Tbody>
            </Table>
          )}
        </Card>
      </Stack>

      <Modal opened={addOpened} onClose={closeAdd} title="Add wallets to group" size="lg">
        <Stack>
          <MultiSelect
            label="Wallets"
            placeholder={selectableAccountOptions.length ? 'Select wallets from Accounts…' : 'No wallets available'}
            data={selectableAccountOptions}
            value={selectedKeys}
            onChange={setSelectedKeys}
            searchable
            clearable
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={closeAdd} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => void handleAddMembers()} loading={isSaving} disabled={!selectedKeys.length}>
              Add
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
