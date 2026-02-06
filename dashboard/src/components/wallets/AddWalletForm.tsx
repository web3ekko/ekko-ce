/**
 * Add Wallet Form Component
 *
 * Form for adding a wallet to the user's Accounts group.
 */

import { useState } from 'react'
import {
  Stack,
  TextInput,
  Select,
  Button,
  Group,
  Text,
  Alert,
} from '@mantine/core'
import {
  IconWallet,
  IconCurrencyBitcoin,
  IconAlertCircle,
  IconCheck,
} from '@tabler/icons-react'
import type { AccountsAddWalletRequest } from '../../services/groups-api'

interface AddWalletFormProps {
  onSubmit: (data: AccountsAddWalletRequest) => void
  onCancel: () => void
  isLoading?: boolean
}

const networkOptions = [
  { value: 'ETH', label: 'Ethereum (ETH)' },
  { value: 'BTC', label: 'Bitcoin (BTC)' },
  { value: 'SOL', label: 'Solana (SOL)' },
  { value: 'POLYGON', label: 'Polygon (POLYGON)' },
  { value: 'ARBITRUM', label: 'Arbitrum (ARBITRUM)' },
  { value: 'OPTIMISM', label: 'Optimism (OPTIMISM)' },
  { value: 'AVAX', label: 'Avalanche (AVAX)' },
  { value: 'BASE', label: 'Base (BASE)' },
  { value: 'BSC', label: 'BNB Chain (BSC)' },
]

// Simple address validation patterns
const addressPatterns: Record<string, RegExp> = {
  ETH: /^0x[a-fA-F0-9]{40}$/,
  POLYGON: /^0x[a-fA-F0-9]{40}$/,
  ARBITRUM: /^0x[a-fA-F0-9]{40}$/,
  OPTIMISM: /^0x[a-fA-F0-9]{40}$/,
  AVAX: /^0x[a-fA-F0-9]{40}$/,
  BASE: /^0x[a-fA-F0-9]{40}$/,
  BSC: /^0x[a-fA-F0-9]{40}$/,
  BTC: /^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59}$/,
}

export function AddWalletForm({ onSubmit, onCancel, isLoading }: AddWalletFormProps) {
  const [label, setLabel] = useState('')
  const [subnet, setSubnet] = useState('mainnet')
  const [address, setAddress] = useState('')
  const [network, setNetwork] = useState<string | null>('ETH')
  const [error, setError] = useState<string | null>(null)
  const [addressValid, setAddressValid] = useState<boolean | null>(null)

  const validateAddress = (addr: string, networkSymbol: string): boolean => {
    const pattern = addressPatterns[networkSymbol]
    if (!pattern) return addr.trim().length > 0
    return pattern.test(addr.trim())
  }

  const handleAddressChange = (value: string) => {
    setAddress(value)
    setError(null)

    if (value.length > 0 && network) {
      setAddressValid(validateAddress(value, network))
    } else {
      setAddressValid(null)
    }
  }

  const handleNetworkChange = (value: string | null) => {
    setNetwork(value)
    setError(null)

    // Re-validate address when network changes
    if (address.length > 0 && value) {
      setAddressValid(validateAddress(address, value))
    }
  }

  const handleSubmit = () => {
    // Validation
    if (!address.trim()) {
      setError('Wallet address is required')
      return
    }

    if (!network) {
      setError('Please select a network')
      return
    }

    if (!subnet.trim()) {
      setError('Subnet is required')
      return
    }

    if (!validateAddress(address, network)) {
      setError(`Invalid ${network} address format`)
      return
    }

    const memberKey = `${network.toUpperCase()}:${subnet.trim().toLowerCase()}:${address.trim()}`

    onSubmit({ member_key: memberKey, label: label.trim() || undefined })
  }

  return (
    <Stack gap="md">
      {error && (
        <Alert color="red" icon={<IconAlertCircle size={16} />}>
          {error}
        </Alert>
      )}

      <Select
        label="Network"
        placeholder="Select network"
        data={networkOptions}
        value={network}
        onChange={handleNetworkChange}
        leftSection={<IconCurrencyBitcoin size={16} />}
        required
      />

      <TextInput
        label="Subnet"
        placeholder="mainnet"
        value={subnet}
        onChange={(e) => setSubnet(e.target.value)}
        description="Use 'mainnet' unless you know you need a testnet/subnet"
        required
      />

      <TextInput
        label="Wallet Address"
        placeholder={network === 'BTC' ? 'bc1... or 1... or 3...' : '0x...'}
        value={address}
        onChange={(e) => handleAddressChange(e.target.value)}
        leftSection={<IconWallet size={16} />}
        rightSection={
          addressValid === true ? (
            <IconCheck size={16} color="green" />
          ) : addressValid === false ? (
            <IconAlertCircle size={16} color="red" />
          ) : null
        }
        error={addressValid === false ? 'Invalid address format' : undefined}
        required
        styles={{
          input: { fontFamily: 'monospace', fontSize: 13 },
        }}
      />

      <TextInput
        label="Label (optional)"
        placeholder="e.g., Main Wallet, Treasury"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        description="Shown in notifications when available"
      />

      <Text size="xs" c="dimmed">
        The wallet will be monitored for transactions and balance changes.
      </Text>

      <Group justify="flex-end" gap="sm" mt="sm">
        <Button variant="subtle" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          loading={isLoading}
          disabled={!address || !network || !subnet}
          style={{ backgroundColor: '#2563EB' }}
        >
          Add Wallet
        </Button>
      </Group>
    </Stack>
  )
}
