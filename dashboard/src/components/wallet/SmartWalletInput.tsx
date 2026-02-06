/**
 * Smart Wallet Input Component
 * 
 * Wallet address input with real-time validation,
 * multi-chain support, and debounced verification
 */

import { useState, useEffect, useCallback } from 'react'
import {
  TextInput,
  Select,
  Group,
  Stack,
  Badge,
  Loader,
  Text,
  Paper,
  ThemeIcon,
  Transition,
  ActionIcon,
  Tooltip,
  Alert,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import {
  IconWallet,
  IconCheck,
  IconX,
  IconAlertCircle,
  IconCopy,
  IconQrcode,
  IconCurrencyEthereum,
  IconCurrencyBitcoin,
  IconCurrencySolana,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'

// Chain configurations
const CHAIN_CONFIGS = {
  ethereum: {
    name: 'Ethereum',
    symbol: 'ETH',
    icon: IconCurrencyEthereum,
    color: 'blue',
    addressPattern: /^0x[a-fA-F0-9]{40}$/,
    placeholder: '0x742d35Cc6634C0532925a3b844Bc9e7595f6cE9B',
    explorerUrl: 'https://etherscan.io/address/',
  },
  bitcoin: {
    name: 'Bitcoin',
    symbol: 'BTC',
    icon: IconCurrencyBitcoin,
    color: 'orange',
    addressPattern: /^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$/,
    placeholder: 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
    explorerUrl: 'https://www.blockchain.com/btc/address/',
  },
  solana: {
    name: 'Solana',
    symbol: 'SOL',
    icon: IconCurrencySolana,
    color: 'green',
    addressPattern: /^[1-9A-HJ-NP-Za-km-z]{32,44}$/,
    placeholder: '7EYnhQoR9YM3N7UoaKRoA44Uy8JeaZV3qyouov87awMs',
    explorerUrl: 'https://explorer.solana.com/address/',
  },
  avalanche: {
    name: 'Avalanche',
    symbol: 'AVAX',
    icon: IconWallet,
    color: 'red',
    addressPattern: /^0x[a-fA-F0-9]{40}$/,
    placeholder: '0x742d35Cc6634C0532925a3b844Bc9e7595f6cE9B',
    explorerUrl: 'https://snowtrace.io/address/',
  },
  polygon: {
    name: 'Polygon',
    symbol: 'MATIC',
    icon: IconWallet,
    color: 'violet',
    addressPattern: /^0x[a-fA-F0-9]{40}$/,
    placeholder: '0x742d35Cc6634C0532925a3b844Bc9e7595f6cE9B',
    explorerUrl: 'https://polygonscan.com/address/',
  },
}

type ChainType = keyof typeof CHAIN_CONFIGS
type ValidationStatus = 'idle' | 'validating' | 'valid' | 'invalid' | 'error'

interface ValidationResult {
  status: ValidationStatus
  message?: string
  balance?: string
  isContract?: boolean
  lastActivity?: string
}

interface SmartWalletInputProps {
  value?: string
  chain?: ChainType
  onChange?: (value: string, chain: ChainType, isValid: boolean) => void
  onValidation?: (result: ValidationResult) => void
  label?: string
  placeholder?: string
  required?: boolean
  disabled?: boolean
  showBalance?: boolean
  showExplorerLink?: boolean
}

export function SmartWalletInput({
  value = '',
  chain: initialChain = 'ethereum',
  onChange,
  onValidation,
  label = 'Wallet Address',
  placeholder,
  required = false,
  disabled = false,
  showBalance = true,
  showExplorerLink = true,
}: SmartWalletInputProps) {
  const [address, setAddress] = useState(value)
  const [selectedChain, setSelectedChain] = useState<ChainType>(initialChain)
  const [validationResult, setValidationResult] = useState<ValidationResult>({
    status: 'idle',
  })
  const [debouncedAddress] = useDebouncedValue(address, 500)
  
  const chainConfig = CHAIN_CONFIGS[selectedChain]
  const ChainIcon = chainConfig.icon

  // Validate address format
  const validateFormat = useCallback((addr: string, chain: ChainType): boolean => {
    if (!addr) return false
    const config = CHAIN_CONFIGS[chain]
    return config.addressPattern.test(addr)
  }, [])

  // Mock API validation (replace with real API call)
  const validateOnChain = useCallback(async (addr: string, chain: ChainType): Promise<ValidationResult> => {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // Mock validation logic
    const isValid = validateFormat(addr, chain)
    
    if (!isValid) {
      return {
        status: 'invalid',
        message: `Invalid ${CHAIN_CONFIGS[chain].name} address format`,
      }
    }

    // Mock successful validation with random data
    return {
      status: 'valid',
      message: 'Valid wallet address',
      balance: `${(Math.random() * 10).toFixed(4)} ${CHAIN_CONFIGS[chain].symbol}`,
      isContract: Math.random() > 0.8,
      lastActivity: '2 days ago',
    }
  }, [validateFormat])

  // Handle validation
  useEffect(() => {
    if (!debouncedAddress) {
      setValidationResult({ status: 'idle' })
      return
    }

    // Quick format check
    if (!validateFormat(debouncedAddress, selectedChain)) {
      setValidationResult({
        status: 'invalid',
        message: `Invalid ${chainConfig.name} address format`,
      })
      onChange?.(debouncedAddress, selectedChain, false)
      return
    }

    // Start validation
    setValidationResult({ status: 'validating' })

    // Perform on-chain validation
    validateOnChain(debouncedAddress, selectedChain)
      .then(result => {
        setValidationResult(result)
        onChange?.(debouncedAddress, selectedChain, result.status === 'valid')
        onValidation?.(result)
      })
      .catch(error => {
        setValidationResult({
          status: 'error',
          message: 'Unable to validate address',
        })
        onChange?.(debouncedAddress, selectedChain, false)
      })
  }, [debouncedAddress, selectedChain, validateFormat, validateOnChain, onChange, onValidation, chainConfig.name])

  const handleAddressChange = (newAddress: string) => {
    setAddress(newAddress)
  }

  const handleChainChange = (newChain: string | null) => {
    if (newChain && newChain in CHAIN_CONFIGS) {
      setSelectedChain(newChain as ChainType)
      // Re-validate with new chain
      if (address) {
        setValidationResult({ status: 'idle' })
      }
    }
  }

  const copyAddress = () => {
    navigator.clipboard.writeText(address)
    // You could show a notification here
  }

  const getStatusIcon = () => {
    switch (validationResult.status) {
      case 'validating':
        return <Loader size="xs" />
      case 'valid':
        return <IconCheck size={16} color="green" />
      case 'invalid':
      case 'error':
        return <IconX size={16} color="red" />
      default:
        return null
    }
  }

  const getStatusColor = () => {
    switch (validationResult.status) {
      case 'valid':
        return 'green'
      case 'invalid':
      case 'error':
        return 'red'
      default:
        return undefined
    }
  }

  return (
    <Stack spacing="xs">
      <Group position="apart" align="flex-end" noWrap>
        <Select
          label="Blockchain"
          value={selectedChain}
          onChange={handleChainChange}
          data={Object.entries(CHAIN_CONFIGS).map(([key, config]) => ({
            value: key,
            label: config.name,
          }))}
          icon={<ChainIcon size={16} />}
          styles={{ root: { width: 150 } }}
          disabled={disabled}
        />
        
        <TextInput
          label={label}
          placeholder={placeholder || chainConfig.placeholder}
          value={address}
          onChange={(e) => handleAddressChange(e.target.value)}
          required={required}
          disabled={disabled}
          error={validationResult.status === 'invalid' && validationResult.message}
          icon={<IconWallet size={16} />}
          rightSection={
            <Group spacing={4} noWrap>
              {getStatusIcon()}
              {address && (
                <>
                  <Tooltip label="Copy address">
                    <ActionIcon size="sm" onClick={copyAddress}>
                      <IconCopy size={14} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Scan QR code">
                    <ActionIcon size="sm">
                      <IconQrcode size={14} />
                    </ActionIcon>
                  </Tooltip>
                </>
              )}
            </Group>
          }
          rightSectionWidth={address ? 80 : 30}
          styles={{
            root: { flex: 1 },
            input: {
              borderColor: getStatusColor() ? `var(--mantine-color-${getStatusColor()}-6)` : undefined,
            },
          }}
        />
      </Group>

      {/* Validation Result */}
      <AnimatePresence mode="wait">
        {validationResult.status === 'valid' && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Paper p="sm" radius="sm" withBorder style={{ borderColor: 'var(--mantine-color-green-6)' }}>
              <Stack spacing="xs">
                <Group spacing="xs">
                  <ThemeIcon size="sm" color="green" variant="light" radius="xl">
                    <IconCheck size={14} />
                  </ThemeIcon>
                  <Text size="sm" weight={500} color="green">
                    Valid {chainConfig.name} Address
                  </Text>
                  {validationResult.isContract && (
                    <Badge size="xs" color="blue" variant="light">
                      Contract
                    </Badge>
                  )}
                </Group>
                
                {showBalance && validationResult.balance && (
                  <Group position="apart">
                    <Text size="xs" color="dimmed">Balance:</Text>
                    <Text size="xs" weight={500}>{validationResult.balance}</Text>
                  </Group>
                )}
                
                {validationResult.lastActivity && (
                  <Group position="apart">
                    <Text size="xs" color="dimmed">Last Activity:</Text>
                    <Text size="xs">{validationResult.lastActivity}</Text>
                  </Group>
                )}
                
                {showExplorerLink && (
                  <Tooltip label="View on blockchain explorer">
                    <Text
                      size="xs"
                      color="blue"
                      component="a"
                      href={`${chainConfig.explorerUrl}${address}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ cursor: 'pointer' }}
                    >
                      View on {chainConfig.name} Explorer →
                    </Text>
                  </Tooltip>
                )}
              </Stack>
            </Paper>
          </motion.div>
        )}

        {validationResult.status === 'error' && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Alert
              icon={<IconAlertCircle size={16} />}
              color="red"
              variant="light"
            >
              <Text size="sm">{validationResult.message}</Text>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>
    </Stack>
  )
}