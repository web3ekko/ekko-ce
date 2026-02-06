/**
 * Wallets Page
 *
 * Provides CRUD for:
 * - Accounts (system wallet group): add/remove wallets
 * - Wallet Groups (user groups): discover/manage via Wallet Groups page
 * - Wallet Import: bulk add wallets to Accounts
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Tooltip,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconCheck,
  IconCopy,
  IconPlus,
  IconSearch,
  IconTrash,
  IconUpload,
  IconUsers,
  IconWallet,
} from '@tabler/icons-react'
import { BulkImportModal } from '../components/ui/BulkImportModal'
import { AddWalletModal } from '../components/wallets/AddWalletModal'
import { useWalletStore } from '../store/wallets'
import { usePersonalizationStore } from '../store/personalization'
import groupsApiService from '../services/groups-api'
import { truncateMiddle } from '../utils/wallet-display'

function encodeWalletKeyForRoute(walletKey: string): string {
  return encodeURIComponent(walletKey)
}

type ImportRow = {
  network: string
  subnet: string
  address: string
  label?: string
  owner_verified?: boolean
}

const accountsCsvTemplate = `network,subnet,address,label,owner_verified
ETH,mainnet,0x71C7656EC7ab88b098defB751B7401B5f6d8976F,Treasury,false
BTC,mainnet,bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh,Savings,false`

const accountsJsonTemplate = `[
  {
    "network": "ETH",
    "subnet": "mainnet",
    "address": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F",
    "label": "Treasury",
    "owner_verified": false
  }
]`

function parseCsv(data: string): ImportRow[] {
  const lines = data.trim().split('\n').filter(Boolean)
  if (lines.length < 2) return []

  const headers = lines[0].split(',').map((h) => h.trim().toLowerCase())
  const rows: ImportRow[] = []

  for (const line of lines.slice(1)) {
    const values = line.split(',').map((v) => v.trim())
    const record: Record<string, string> = {}
    headers.forEach((header, index) => {
      record[header] = values[index] || ''
    })

    const network = (record.network || record.blockchain || record.chain || '').trim()
    const subnet = (record.subnet || 'mainnet').trim()
    const address = (record.address || '').trim()
    const label = (record.label || record.name || '').trim()
    const ownerVerifiedRaw = (record.owner_verified || record.ownerverified || '').trim().toLowerCase()
    const owner_verified = ownerVerifiedRaw === 'true' || ownerVerifiedRaw === '1' || ownerVerifiedRaw === 'yes'

    if (!network || !subnet || !address) continue

    rows.push({
      network,
      subnet,
      address,
      label: label || undefined,
      owner_verified,
    })
  }

  return rows
}

function parseJson(data: string): ImportRow[] {
  const parsed = JSON.parse(data)
  if (!Array.isArray(parsed)) return []

  return parsed
    .map((row) => {
      const network = String(row.network || '').trim()
      const subnet = String(row.subnet || 'mainnet').trim()
      const address = String(row.address || '').trim()
      const label = row.label ? String(row.label).trim() : undefined
      const owner_verified = Boolean(row.owner_verified)
      if (!network || !subnet || !address) return null
      return { network, subnet, address, label, owner_verified }
    })
    .filter((row): row is ImportRow => row !== null)
}

export function WalletsPage() {
  const navigate = useNavigate()
  const {
    accounts,
    accountsGroup,
    walletGroups,
    isLoading,
    error,
    loadAccounts,
    loadWalletGroups,
    removeAccountWallet,
  } = useWalletStore()

  const loadChains = usePersonalizationStore((s) => s.loadChains)
  const loadWalletNicknames = usePersonalizationStore((s) => s.loadWalletNicknames)
  const getChainId = usePersonalizationStore((s) => s.getChainId)
  const getWalletNickname = usePersonalizationStore((s) => s.getWalletNickname)

  const [activeTab, setActiveTab] = useState<string | null>('accounts')
  const [searchQuery, setSearchQuery] = useState('')
  const [addWalletOpened, { open: openAddWallet, close: closeAddWallet }] = useDisclosure(false)
  const [bulkImportOpened, { open: openBulkImport, close: closeBulkImport }] = useDisclosure(false)

  useEffect(() => {
    void loadAccounts()
    void loadWalletGroups()
    void loadWalletNicknames()
    void loadChains()
  }, [loadAccounts, loadWalletGroups, loadWalletNicknames, loadChains])

  const getDisplayLabel = (wallet: { label?: string; address: string; network: string }): string => {
    const nickname = getWalletNickname(wallet.address, getChainId(wallet.network))
    return wallet.label || nickname || truncateMiddle(wallet.address)
  }

  const filteredAccounts = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return accounts
    return accounts.filter((w) => {
      const nickname = getWalletNickname(w.address, getChainId(w.network))
      return (
        (w.label || '').toLowerCase().includes(q) ||
        (nickname || '').toLowerCase().includes(q) ||
        w.wallet_key.toLowerCase().includes(q) ||
        w.address.toLowerCase().includes(q)
      )
    })
  }, [accounts, searchQuery, getWalletNickname, getChainId])

  const handleCopy = async (value: string) => {
    await navigator.clipboard.writeText(value)
    notifications.show({
      title: 'Copied',
      message: 'Copied to clipboard',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
  }

  const handleRemoveAccountWallet = async (walletKey: string) => {
    if (!confirm('Remove this wallet from your Accounts?')) return
    await removeAccountWallet(walletKey)
  }

  const handleBulkImport = async (
    data: string,
    format: 'csv' | 'json'
  ): Promise<{ success: number; failed: number; errors?: string[] }> => {
    const rows = format === 'json' ? parseJson(data) : parseCsv(data)

    const wallets = rows.map((row) => ({
      member_key: `${row.network.toUpperCase()}:${row.subnet.toLowerCase()}:${row.address}`,
      label: row.label,
      owner_verified: row.owner_verified,
    }))

    if (!wallets.length) {
      return { success: 0, failed: 0 }
    }

    const resp = await groupsApiService.addWalletsToAccounts({ wallets })
    await loadAccounts()

    const errors: string[] = (resp.errors || []).map((e) => {
      const message =
        typeof e.errors === 'string'
          ? e.errors
          : JSON.stringify(e.errors)
      return `${e.member_key || `row ${e.row_number}`}: ${message}`
    })

    const success = resp.added + (resp.already_exists?.length || 0)
    const failed = resp.errors?.length || 0

    return { success, failed, errors: errors.length ? errors : undefined }
  }

  if (isLoading && accounts.length === 0 && walletGroups.length === 0) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Loader size="lg" color="blue" />
          <Text c="dimmed">Loading wallets…</Text>
        </Stack>
      </Center>
    )
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between">
          <div>
            <Title order={1} c="#0F172A">
              Wallets
            </Title>
            <Text c="#475569" mt="xs">
              Manage Accounts (your wallets), wallet groups, and imports
            </Text>
          </div>
          <Group gap="sm">
            <Button
              variant="light"
              leftSection={<IconUpload size={16} />}
              onClick={openBulkImport}
            >
              Import
            </Button>
            <Button
              leftSection={<IconPlus size={16} />}
              style={{ backgroundColor: '#2563EB' }}
              onClick={openAddWallet}
            >
              Add wallet
            </Button>
          </Group>
        </Group>

        {error && (
          <Alert color="red" title="Error">
            {error}
          </Alert>
        )}

        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="accounts" leftSection={<IconWallet size={16} />}>
              Accounts
              <Badge size="sm" variant="light" color="gray" ml="xs">
                {accounts.length}
              </Badge>
            </Tabs.Tab>
            <Tabs.Tab value="groups" leftSection={<IconUsers size={16} />}>
              Groups
              <Badge size="sm" variant="light" color="gray" ml="xs">
                {walletGroups.length}
              </Badge>
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="accounts" pt="xl">
            <Stack gap="md">
              <Group justify="space-between" align="center">
                <TextInput
                  placeholder="Search accounts…"
                  leftSection={<IconSearch size={16} />}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.currentTarget.value)}
                  style={{ flex: 1, maxWidth: 420 }}
                />
                <Badge variant="light" color="gray">
                  {accountsGroup ? 'Accounts created' : 'Accounts not created yet'}
                </Badge>
              </Group>

              {filteredAccounts.length === 0 ? (
                <Card withBorder padding="xl" radius="md">
                  <Stack gap="sm" align="center">
                    <IconWallet size={28} color="#64748B" />
                    <Title order={3}>Add your first wallet</Title>
                    <Text c="dimmed" ta="center" maw={420}>
                      Accounts is your private list of wallets. Add a wallet to start monitoring and to use it as a
                      target for alert groups.
                    </Text>
                    <Group>
                      <Button onClick={openAddWallet} style={{ backgroundColor: '#2563EB' }}>
                        Add wallet
                      </Button>
                      <Button variant="light" onClick={openBulkImport}>
                        Import
                      </Button>
                    </Group>
                  </Stack>
                </Card>
              ) : (
                <Card withBorder padding="md" radius="md">
                  <Table verticalSpacing="sm">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Label</Table.Th>
                        <Table.Th>Network</Table.Th>
                        <Table.Th>Address</Table.Th>
                        <Table.Th>Verified</Table.Th>
                        <Table.Th style={{ width: 120 }} />
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {filteredAccounts.map((wallet) => (
                        <Table.Tr key={wallet.wallet_key}>
                          <Table.Td>
                            <Text fw={600} size="sm">
                              {getDisplayLabel(wallet)}
                            </Text>
                            <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                              {wallet.wallet_key}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Badge variant="light" color="blue">
                              {wallet.network}:{wallet.subnet}
                            </Badge>
                          </Table.Td>
                          <Table.Td>
                            <Text size="sm" style={{ fontFamily: 'monospace' }}>
                              {truncateMiddle(wallet.address)}
                            </Text>
                          </Table.Td>
                          <Table.Td>
                            <Badge variant="dot" color={wallet.owner_verified ? 'green' : 'gray'}>
                              {wallet.owner_verified ? 'Verified' : 'Unverified'}
                            </Badge>
                          </Table.Td>
                          <Table.Td>
                            <Group gap={6} justify="flex-end">
                              <Tooltip label="Copy wallet key">
                                <ActionIcon
                                  variant="subtle"
                                  onClick={() => void handleCopy(wallet.wallet_key)}
                                >
                                  <IconCopy size={16} />
                                </ActionIcon>
                              </Tooltip>
                              <Tooltip label="View details">
                                <ActionIcon
                                  variant="subtle"
                                  onClick={() => navigate(`/dashboard/wallets/${encodeWalletKeyForRoute(wallet.wallet_key)}`)}
                                >
                                  <IconWallet size={16} />
                                </ActionIcon>
                              </Tooltip>
                              <Tooltip label="Remove from Accounts">
                                <ActionIcon
                                  variant="subtle"
                                  color="red"
                                  onClick={() => void handleRemoveAccountWallet(wallet.wallet_key)}
                                >
                                  <IconTrash size={16} />
                                </ActionIcon>
                              </Tooltip>
                            </Group>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Card>
              )}
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="groups" pt="xl">
            <Stack gap="md">
              <Group justify="space-between">
                <div>
                  <Title order={3}>Wallet Groups</Title>
                  <Text c="dimmed" size="sm">
                    Organize wallets into groups and use groups as alert targets.
                  </Text>
                </div>
                <Button onClick={() => navigate('/dashboard/wallets/groups')} style={{ backgroundColor: '#2563EB' }}>
                  Manage groups
                </Button>
              </Group>

              {walletGroups.length === 0 ? (
                <Card withBorder padding="lg" radius="md">
                  <Text c="dimmed">
                    No wallet groups yet. Create one in Wallet Groups.
                  </Text>
                </Card>
              ) : (
                <Card withBorder padding="md" radius="md">
                  <Table verticalSpacing="sm">
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Name</Table.Th>
                        <Table.Th>Visibility</Table.Th>
                        <Table.Th>Members</Table.Th>
                        <Table.Th style={{ width: 120 }} />
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {walletGroups.map((group) => {
                        const visibility = (group.settings as { visibility?: string } | undefined)?.visibility || 'private'
                        return (
                          <Table.Tr key={group.id}>
                            <Table.Td>
                              <Text fw={600} size="sm">{group.name}</Text>
                              <Text size="xs" c="dimmed">{group.description || ''}</Text>
                            </Table.Td>
                            <Table.Td>
                              <Badge variant="light" color={visibility === 'public' ? 'blue' : 'gray'}>
                                {visibility}
                              </Badge>
                            </Table.Td>
                            <Table.Td>
                              <Badge variant="light" color="gray">
                                {group.member_count || 0}
                              </Badge>
                            </Table.Td>
                            <Table.Td>
                              <Group justify="flex-end" gap={6}>
                                <Tooltip label="View group">
                                  <ActionIcon
                                    variant="subtle"
                                    onClick={() => navigate(`/dashboard/wallets/groups/${group.id}`)}
                                  >
                                    <IconUsers size={16} />
                                  </ActionIcon>
                                </Tooltip>
                              </Group>
                            </Table.Td>
                          </Table.Tr>
                        )
                      })}
                    </Table.Tbody>
                  </Table>
                </Card>
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>

      <AddWalletModal
        opened={addWalletOpened}
        onClose={closeAddWallet}
        onWalletAdded={() => {
          void loadWalletGroups()
        }}
      />

      <BulkImportModal
        opened={bulkImportOpened}
        onClose={closeBulkImport}
        title="Import Wallets to Accounts"
        description="Upload CSV/JSON to add wallets to your Accounts group."
        itemType="wallets"
        csvTemplate={accountsCsvTemplate}
        jsonTemplate={accountsJsonTemplate}
        onImport={handleBulkImport}
      />
    </Container>
  )
}
