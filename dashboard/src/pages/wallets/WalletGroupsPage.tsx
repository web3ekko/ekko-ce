/**
 * Wallet Groups Page
 *
 * CRUD for wallet groups (GenericGroup group_type="wallet").
 * Includes the system Accounts group as a non-editable entry.
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Container,
  Grid,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Select,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
  Center,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconCheck, IconFolderPlus, IconSearch } from '@tabler/icons-react'
import groupsApiService from '../../services/groups-api'
import type { GenericGroup } from '../../services/groups-api'
import { useWalletStore } from '../../store/wallets'
import { usePersonalizationStore } from '../../store/personalization'
import { WalletGroupCard } from '../../components/wallets/WalletGroupCard'
import { truncateMiddle } from '../../utils/wallet-display'

const GROUP_COLORS = [
  '#2563EB', '#14B8A6', '#10B981', '#FB923C',
  '#EF4444', '#0EA5E9', '#3B82F6', '#0F766E',
]

const GROUP_ICONS = ['💼', '🏦', '🌱', '💎', '🔒', '🚀', '📊', '🌐']

function isSystemAccountsGroup(group: GenericGroup): boolean {
  const settings = group.settings as { system_key?: string } | undefined
  return settings?.system_key === 'accounts'
}

export function WalletGroupsPage() {
  const navigate = useNavigate()
  const {
    accounts,
    walletGroups,
    isLoading,
    error,
    loadAccounts,
    loadWalletGroups,
    createWalletGroup,
    updateWalletGroup,
    deleteWalletGroup,
  } = useWalletStore()

  const loadChains = usePersonalizationStore((s) => s.loadChains)
  const loadWalletNicknames = usePersonalizationStore((s) => s.loadWalletNicknames)
  const getChainId = usePersonalizationStore((s) => s.getChainId)
  const getWalletNickname = usePersonalizationStore((s) => s.getWalletNickname)

  const [searchQuery, setSearchQuery] = useState('')
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure(false)
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false)

  const [selectedGroup, setSelectedGroup] = useState<GenericGroup | null>(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formVisibility, setFormVisibility] = useState<'private' | 'public'>('private')
  const [formColor, setFormColor] = useState(GROUP_COLORS[0])
  const [formIcon, setFormIcon] = useState(GROUP_ICONS[0])
  const [formWalletKeys, setFormWalletKeys] = useState<string[]>([])
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    void loadAccounts()
    void loadWalletGroups()
    void loadWalletNicknames()
    void loadChains()
  }, [loadAccounts, loadWalletGroups, loadWalletNicknames, loadChains])

  const walletKeyOptions = useMemo(() => {
    return accounts.map((w) => ({
      value: w.wallet_key,
      label: `${w.label || getWalletNickname(w.address, getChainId(w.network)) || truncateMiddle(w.address)} · ${w.network}:${w.subnet}`,
    }))
  }, [accounts, getWalletNickname, getChainId])

  const filteredGroups = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return walletGroups
    return walletGroups.filter((group) => {
      return (
        group.name.toLowerCase().includes(q) ||
        (group.description || '').toLowerCase().includes(q)
      )
    })
  }, [walletGroups, searchQuery])

  const resetForm = () => {
    setFormName('')
    setFormDescription('')
    setFormVisibility('private')
    setFormColor(GROUP_COLORS[0])
    setFormIcon(GROUP_ICONS[0])
    setFormWalletKeys([])
    setSelectedGroup(null)
  }

  const openEditForGroup = async (group: GenericGroup) => {
    if (isSystemAccountsGroup(group)) return

    setIsSaving(true)
    try {
      const fullGroup = await groupsApiService.getGroup(group.id)
      const settings = fullGroup.settings as { visibility?: string; color?: string; icon?: string } | undefined

      setSelectedGroup(fullGroup)
      setFormName(fullGroup.name)
      setFormDescription(fullGroup.description || '')
      setFormVisibility((settings?.visibility === 'public' ? 'public' : 'private') as 'private' | 'public')
      setFormColor(settings?.color || GROUP_COLORS[0])
      setFormIcon(settings?.icon || GROUP_ICONS[0])
      setFormWalletKeys(fullGroup.member_keys || [])
      openEdit()
    } catch (error) {
      console.error('Failed to load group for edit:', error)
      notifications.show({
        title: 'Error',
        message: 'Failed to load group details',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleCreate = async () => {
    if (!formName.trim()) return
    setIsSaving(true)
    try {
      const newGroup = await createWalletGroup({
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        settings: { visibility: formVisibility, color: formColor, icon: formIcon },
      })

      if (formWalletKeys.length) {
        const members = formWalletKeys.map((walletKey) => {
          const account = accounts.find((a) => a.wallet_key === walletKey)
          return {
            member_key: walletKey,
            label: account?.label || '',
          }
        })
        await groupsApiService.addMembers(newGroup.id, { members })
        await loadWalletGroups()
      }

      notifications.show({
        title: 'Group Created',
        message: 'Wallet group created successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      closeCreate()
      resetForm()
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to create wallet group',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleUpdate = async () => {
    if (!selectedGroup || !formName.trim()) return
    setIsSaving(true)
    try {
      const fullGroup = await groupsApiService.getGroup(selectedGroup.id)
      const currentKeys = new Set(fullGroup.member_keys || [])
      const desiredKeys = new Set(formWalletKeys)

      await updateWalletGroup(selectedGroup.id, {
        name: formName.trim(),
        description: formDescription.trim() || '',
        settings: { visibility: formVisibility, color: formColor, icon: formIcon },
      })

      const toAdd = [...desiredKeys].filter((k) => !currentKeys.has(k))
      const toRemove = [...currentKeys].filter((k) => !desiredKeys.has(k))

      if (toAdd.length) {
        await groupsApiService.addMembers(selectedGroup.id, {
          members: toAdd.map((walletKey) => {
            const account = accounts.find((a) => a.wallet_key === walletKey)
            return { member_key: walletKey, label: account?.label || '' }
          }),
        })
      }

      if (toRemove.length) {
        await groupsApiService.removeMembers(selectedGroup.id, {
          members: toRemove.map((walletKey) => ({ member_key: walletKey })),
        })
      }

      await loadWalletGroups()

      notifications.show({
        title: 'Group Updated',
        message: 'Wallet group updated successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      closeEdit()
      resetForm()
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: error instanceof Error ? error.message : 'Failed to update wallet group',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (group: GenericGroup) => {
    if (isSystemAccountsGroup(group)) return
    if (!confirm(`Delete "${group.name}"?`)) return
    setIsSaving(true)
    try {
      await deleteWalletGroup(group.id)
      notifications.show({
        title: 'Group Deleted',
        message: 'Wallet group deleted',
        color: 'orange',
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading && walletGroups.length === 0) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Loader size="lg" color="blue" />
          <Text c="dimmed">Loading wallet groups…</Text>
        </Stack>
      </Center>
    )
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between">
          <div>
            <Title order={1} c="#0F172A">Wallet Groups</Title>
            <Text c="#475569" mt="xs">
              Organize wallets into groups and use groups as alert targets
            </Text>
          </div>
          <Group>
            <Button
              variant="light"
              onClick={() => navigate('/dashboard/wallets')}
            >
              Back to Wallets
            </Button>
            <Button
              leftSection={<IconFolderPlus size={16} />}
              style={{ backgroundColor: '#2563EB' }}
              onClick={openCreate}
            >
              Create group
            </Button>
          </Group>
        </Group>

        {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red">
            {error}
          </Alert>
        )}

        <TextInput
          placeholder="Search groups…"
          leftSection={<IconSearch size={16} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.currentTarget.value)}
          style={{ maxWidth: 420 }}
        />

        <Grid>
          {filteredGroups.map((group) => (
            <Grid.Col key={group.id} span={{ base: 12, md: 6, lg: 4 }}>
              <WalletGroupCard
                group={group}
                walletCount={group.member_count || 0}
                onView={() => navigate(`/dashboard/wallets/groups/${group.id}`)}
                onEdit={() => void openEditForGroup(group)}
                onDelete={() => void handleDelete(group)}
              />
            </Grid.Col>
          ))}
        </Grid>

        {filteredGroups.length === 0 && (
          <Center h={200}>
            <Text c="dimmed">No wallet groups found</Text>
          </Center>
        )}
      </Stack>

      <Modal
        opened={createOpened}
        onClose={() => {
          closeCreate()
          resetForm()
        }}
        title="Create Wallet Group"
        size="lg"
      >
        <Stack>
          <TextInput label="Name" value={formName} onChange={(e) => setFormName(e.currentTarget.value)} required />
          <Textarea label="Description" value={formDescription} onChange={(e) => setFormDescription(e.currentTarget.value)} />
          <Select
            label="Visibility"
            data={[
              { value: 'private', label: 'Private' },
              { value: 'public', label: 'Public (subscribable)' },
            ]}
            value={formVisibility}
            onChange={(value) => setFormVisibility((value === 'public' ? 'public' : 'private'))}
            required
          />
          <Select
            label="Color"
            data={GROUP_COLORS.map((c) => ({ value: c, label: c }))}
            value={formColor}
            onChange={(value) => setFormColor(value || GROUP_COLORS[0])}
          />
          <Select
            label="Icon"
            data={GROUP_ICONS.map((i) => ({ value: i, label: i }))}
            value={formIcon}
            onChange={(value) => setFormIcon(value || GROUP_ICONS[0])}
          />
          <MultiSelect
            label="Wallets (optional)"
            placeholder={walletKeyOptions.length ? 'Select wallets from Accounts…' : 'Add wallets to Accounts first'}
            data={walletKeyOptions}
            value={formWalletKeys}
            onChange={setFormWalletKeys}
            searchable
            clearable
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => { closeCreate(); resetForm() }} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => void handleCreate()} loading={isSaving} disabled={!formName.trim()} style={{ backgroundColor: '#2563EB' }}>
              Create
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={editOpened}
        onClose={() => {
          closeEdit()
          resetForm()
        }}
        title={`Edit "${selectedGroup?.name || 'Group'}"`}
        size="lg"
      >
        <Stack>
          <TextInput label="Name" value={formName} onChange={(e) => setFormName(e.currentTarget.value)} required />
          <Textarea label="Description" value={formDescription} onChange={(e) => setFormDescription(e.currentTarget.value)} />
          <Select
            label="Visibility"
            data={[
              { value: 'private', label: 'Private' },
              { value: 'public', label: 'Public (subscribable)' },
            ]}
            value={formVisibility}
            onChange={(value) => setFormVisibility((value === 'public' ? 'public' : 'private'))}
            required
          />
          <Select
            label="Color"
            data={GROUP_COLORS.map((c) => ({ value: c, label: c }))}
            value={formColor}
            onChange={(value) => setFormColor(value || GROUP_COLORS[0])}
          />
          <Select
            label="Icon"
            data={GROUP_ICONS.map((i) => ({ value: i, label: i }))}
            value={formIcon}
            onChange={(value) => setFormIcon(value || GROUP_ICONS[0])}
          />
          <MultiSelect
            label="Wallets"
            placeholder="Select wallets…"
            data={walletKeyOptions}
            value={formWalletKeys}
            onChange={setFormWalletKeys}
            searchable
            clearable
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => { closeEdit(); resetForm() }} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={() => void handleUpdate()} loading={isSaving} disabled={!formName.trim()} style={{ backgroundColor: '#2563EB' }}>
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
