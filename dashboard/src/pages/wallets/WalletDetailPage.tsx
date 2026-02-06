/**
 * Wallet Detail Page (Accounts wallet)
 *
 * Route param is a URL-encoded wallet key: {NETWORK}:{subnet}:{address}
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Group,
  Loader,
  Modal,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft, IconCheck, IconCopy, IconPencil, IconTrash, IconWallet } from '@tabler/icons-react'
import { useWalletStore } from '../../store/wallets'
import { usePersonalizationStore } from '../../store/personalization'
import walletNicknamesApiService from '../../services/wallet-nicknames-api'

function truncateMiddle(value: string, prefix = 10, suffix = 10): string {
  if (value.length <= prefix + suffix + 3) return value
  return `${value.slice(0, prefix)}...${value.slice(-suffix)}`
}

export function WalletDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { accounts, isLoading, loadAccounts, removeAccountWallet, updateAccountWallet } = useWalletStore()
  const loadChains = usePersonalizationStore((s) => s.loadChains)
  const loadWalletNicknames = usePersonalizationStore((s) => s.loadWalletNicknames)
  const getChainId = usePersonalizationStore((s) => s.getChainId)
  const getWalletNickname = usePersonalizationStore((s) => s.getWalletNickname)
  const getWalletNicknameRecord = usePersonalizationStore((s) => s.getWalletNicknameRecord)
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false)
  const [editLabel, setEditLabel] = useState('')
  const [editVerified, setEditVerified] = useState(false)
  const [nicknameValue, setNicknameValue] = useState('')
  const [isSavingNickname, setIsSavingNickname] = useState(false)

  const walletKey = useMemo(() => {
    if (!id) return ''
    try {
      return decodeURIComponent(id)
    } catch {
      return id
    }
  }, [id])

  useEffect(() => {
    if (!accounts.length) {
      void loadAccounts()
    }
    void loadWalletNicknames()
    void loadChains()
  }, [accounts.length, loadAccounts, loadWalletNicknames, loadChains])

  const wallet = useMemo(() => accounts.find((w) => w.wallet_key === walletKey) || null, [accounts, walletKey])
  const nickname = wallet ? getWalletNickname(wallet.address, getChainId(wallet.network)) : null
  const nicknameRecord = wallet ? getWalletNicknameRecord(wallet.address, getChainId(wallet.network)) : null

  useEffect(() => {
    setNicknameValue(nicknameRecord?.custom_name || '')
  }, [nicknameRecord?.id])

  useEffect(() => {
    if (!editOpened) return
    setEditLabel(wallet?.label || '')
    setEditVerified(Boolean(wallet?.owner_verified))
  }, [editOpened, wallet])

  const handleCopy = async () => {
    await navigator.clipboard.writeText(walletKey)
    notifications.show({
      title: 'Copied',
      message: 'Wallet key copied to clipboard',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
  }

  const handleRemove = async () => {
    if (!walletKey) return
    if (!confirm('Remove this wallet from your Accounts?')) return
    await removeAccountWallet(walletKey)
    navigate('/dashboard/wallets')
  }

  const handleSave = async () => {
    await updateAccountWallet(walletKey, {
      label: editLabel.trim(),
      owner_verified: editVerified,
    })
    notifications.show({
      title: 'Updated',
      message: 'Wallet updated',
      color: 'green',
      icon: <IconCheck size={16} />,
    })
    closeEdit()
  }

  const handleSaveNickname = async () => {
    if (!wallet) return

    const chainId = getChainId(wallet.network)
    if (typeof chainId !== 'number') {
      notifications.show({
        title: 'Chain missing',
        message: 'Cannot set nickname because this network does not map to a chain_id yet.',
        color: 'red',
      })
      return
    }

    const nextValue = nicknameValue.trim()
    setIsSavingNickname(true)
    try {
      if (!nextValue) {
        if (nicknameRecord) {
          await walletNicknamesApiService.delete(nicknameRecord.id)
          await loadWalletNicknames()
        }
        notifications.show({
          title: 'Nickname cleared',
          message: 'Wallet nickname removed',
          color: 'orange',
        })
        return
      }

      if (nicknameRecord) {
        await walletNicknamesApiService.update(nicknameRecord.id, { custom_name: nextValue })
      } else {
        await walletNicknamesApiService.create({
          wallet_address: wallet.address,
          chain_id: chainId,
          custom_name: nextValue,
        })
      }

      await loadWalletNicknames()
      notifications.show({
        title: 'Saved',
        message: 'Wallet nickname updated',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } finally {
      setIsSavingNickname(false)
    }
  }

  if (isLoading && !wallet) {
    return (
      <Center h={400}>
        <Stack align="center" gap="md">
          <Loader size="lg" color="blue" />
          <Text c="dimmed">Loading wallet…</Text>
        </Stack>
      </Center>
    )
  }

  if (!walletKey) {
    return (
      <Center h={400}>
        <Text c="dimmed">Missing wallet key</Text>
      </Center>
    )
  }

  return (
    <Container size="md" py="xl">
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
              <Title order={2}>{wallet?.label || nickname || 'Wallet'}</Title>
              {wallet && (
                <Badge variant="dot" color={wallet.owner_verified ? 'green' : 'gray'}>
                  {wallet.owner_verified ? 'Verified' : 'Unverified'}
                </Badge>
              )}
            </Group>
            <Text c="dimmed" style={{ fontFamily: 'monospace' }}>
              {truncateMiddle(walletKey)}
            </Text>
          </div>
          <Group>
            <Tooltip label="Copy wallet key">
              <ActionIcon variant="light" onClick={() => void handleCopy()}>
                <IconCopy size={16} />
              </ActionIcon>
            </Tooltip>
            {wallet && (
              <Tooltip label="Edit label and verification">
                <ActionIcon variant="light" onClick={openEdit}>
                  <IconPencil size={16} />
                </ActionIcon>
              </Tooltip>
            )}
            <Tooltip label="Remove from Accounts">
              <ActionIcon variant="light" color="red" onClick={() => void handleRemove()}>
                <IconTrash size={16} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>

        <Card withBorder padding="lg" radius="md">
          <Group gap="sm" mb="md">
            <IconWallet size={18} />
            <Title order={4}>Details</Title>
          </Group>

          {wallet ? (
            <Stack gap="xs">
              <Group justify="space-between">
                <Text c="dimmed">Network</Text>
                <Text fw={600}>{wallet.network}</Text>
              </Group>
              <Group justify="space-between">
                <Text c="dimmed">Subnet</Text>
                <Text fw={600}>{wallet.subnet}</Text>
              </Group>
              <Group justify="space-between">
                <Text c="dimmed">Address</Text>
                <Text fw={600} style={{ fontFamily: 'monospace' }}>
                  {truncateMiddle(wallet.address)}
                </Text>
              </Group>
              <Group justify="space-between">
                <Text c="dimmed">Added</Text>
                <Text fw={600}>{wallet.added_at ? new Date(wallet.added_at).toLocaleString() : '—'}</Text>
              </Group>
            </Stack>
          ) : (
            <Text c="dimmed">
              This wallet key is not in your Accounts. Add it from the Wallets page if you want to manage it here.
            </Text>
          )}
        </Card>

        {wallet && (
          <Card withBorder padding="lg" radius="md">
            <Group justify="space-between" align="center" mb="md">
              <Title order={4}>Nickname</Title>
              <Badge variant="light" color="gray">
                Fallback
              </Badge>
            </Group>
            <Stack gap="sm">
              <Text size="sm" c="dimmed">
                Used when this wallet has no Accounts label.
              </Text>
              <TextInput
                label="Nickname"
                placeholder="e.g., Cold Storage"
                value={nicknameValue}
                onChange={(e) => setNicknameValue(e.currentTarget.value)}
              />
              <Group justify="flex-end">
                <Button
                  variant="light"
                  color="gray"
                  onClick={() => setNicknameValue(nicknameRecord?.custom_name || '')}
                  disabled={isSavingNickname}
                >
                  Reset
                </Button>
                <Button onClick={() => void handleSaveNickname()} loading={isSavingNickname} style={{ backgroundColor: '#2563EB' }}>
                  Save nickname
                </Button>
              </Group>
            </Stack>
          </Card>
        )}
      </Stack>

      <Modal opened={editOpened} onClose={closeEdit} title="Edit Wallet" size="sm">
        <Stack gap="md">
          <TextInput
            label="Label"
            placeholder="e.g., Treasury"
            value={editLabel}
            onChange={(e) => setEditLabel(e.currentTarget.value)}
          />
          <Switch
            label="Owner verified"
            description="Marks that you control this wallet"
            checked={editVerified}
            onChange={(e) => setEditVerified(e.currentTarget.checked)}
          />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={closeEdit}>
              Cancel
            </Button>
            <Button onClick={() => void handleSave()} style={{ backgroundColor: '#2563EB' }}>
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
