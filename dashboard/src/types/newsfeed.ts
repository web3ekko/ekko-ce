/**
 * Newsfeed Types
 *
 * TypeScript interfaces for the transaction newsfeed that displays
 * blockchain transactions for user's monitored wallets
 */

// Supported blockchain chains for newsfeed
export type NewsfeedChainId =
  | 'ethereum_mainnet'
  | 'ethereum_sepolia'
  | 'polygon_mainnet'
  | 'polygon_mumbai'
  | 'arbitrum_one'
  | 'arbitrum_sepolia'
  | 'optimism_mainnet'
  | 'base_mainnet'
  | 'bsc_mainnet'
  | 'avalanche_mainnet'
  | 'solana_mainnet'
  | 'solana_devnet'
  | 'bitcoin_mainnet'
  | 'bitcoin_testnet'

// Transaction types from DuckLake unified schema
export type NewsfeedTransactionType =
  | 'TRANSFER'
  | 'CONTRACT_CALL'
  | 'CONTRACT_CREATE'
  | 'INTERNAL'
  | 'UNKNOWN'

// Transaction subtypes for more specific categorization
export type NewsfeedTransactionSubtype =
  | 'native_transfer'
  | 'erc20_transfer'
  | 'erc721_transfer'
  | 'erc1155_transfer'
  | 'swap'
  | 'liquidity_add'
  | 'liquidity_remove'
  | 'stake'
  | 'unstake'
  | 'bridge'
  | 'governance_vote'
  | 'contract_deployment'
  | 'unknown'

// Transaction status
export type NewsfeedTransactionStatus =
  | 'SUCCESS'
  | 'FAILED'
  | 'PENDING'

// Single transaction in the newsfeed
export interface NewsfeedTransaction {
  // Core identifiers
  transaction_hash: string
  block_number: number
  block_timestamp: string // ISO 8601

  // Chain information
  chain_id: NewsfeedChainId | string
  network: string
  subnet: string

  // Addresses
  from_address: string
  to_address: string | null

  // Monitored wallet context
  monitored_address: string
  is_sender: boolean

  // Transaction classification
  transaction_type: NewsfeedTransactionType
  transaction_subtype: NewsfeedTransactionSubtype | string | null

  // Value information
  value: string | null // Raw value as string (for big numbers)
  amount_usd: number | null
  gas_price: string | null
  gas_used: number | null

  // Decoded information (from ABI decoder)
  decoded_function_name: string | null
  decoded_function_signature: string | null
  decoded_summary: string | null

  // Status
  status: NewsfeedTransactionStatus
}

// API response for newsfeed transactions
export interface NewsfeedResponse {
  transactions: NewsfeedTransaction[]
  total: number
  monitored_addresses: number
  chains: string[]
}

// API request parameters
export interface NewsfeedParams {
  limit?: number // Default: 50, Max: 500
  offset?: number // Default: 0
  chains?: string // Comma-separated chain_ids
  start_date?: string // ISO 8601 datetime
  transaction_type?: NewsfeedTransactionType
}

// Newsfeed state for UI components
export interface NewsfeedState {
  transactions: NewsfeedTransaction[]
  isLoading: boolean
  error: string | null
  hasMore: boolean
  total: number
  monitoredAddresses: number
  activeChains: string[]
}

// Newsfeed filter options
export interface NewsfeedFilters {
  chains: string[]
  transactionTypes: NewsfeedTransactionType[]
  direction: 'all' | 'sent' | 'received'
  timeRange: 'hour' | 'day' | 'week' | 'month' | 'all'
}

// Helper type for direction display
export type TransactionDirection = 'sent' | 'received' | 'contract'

// Chain metadata for display purposes
export interface ChainMetadata {
  id: string
  name: string
  shortName: string
  icon: string
  color: string
  explorerUrl: string
  explorerTxPath: string
}

// Chain metadata mapping
export const CHAIN_METADATA: Record<string, ChainMetadata> = {
  ethereum_mainnet: {
    id: 'ethereum_mainnet',
    name: 'Ethereum',
    shortName: 'ETH',
    icon: 'ethereum',
    color: '#627EEA',
    explorerUrl: 'https://etherscan.io',
    explorerTxPath: '/tx/',
  },
  ethereum_sepolia: {
    id: 'ethereum_sepolia',
    name: 'Ethereum Sepolia',
    shortName: 'ETH',
    icon: 'ethereum',
    color: '#627EEA',
    explorerUrl: 'https://sepolia.etherscan.io',
    explorerTxPath: '/tx/',
  },
  polygon_mainnet: {
    id: 'polygon_mainnet',
    name: 'Polygon',
    shortName: 'MATIC',
    icon: 'polygon',
    color: '#8247E5',
    explorerUrl: 'https://polygonscan.com',
    explorerTxPath: '/tx/',
  },
  arbitrum_one: {
    id: 'arbitrum_one',
    name: 'Arbitrum',
    shortName: 'ARB',
    icon: 'arbitrum',
    color: '#28A0F0',
    explorerUrl: 'https://arbiscan.io',
    explorerTxPath: '/tx/',
  },
  optimism_mainnet: {
    id: 'optimism_mainnet',
    name: 'Optimism',
    shortName: 'OP',
    icon: 'optimism',
    color: '#FF0420',
    explorerUrl: 'https://optimistic.etherscan.io',
    explorerTxPath: '/tx/',
  },
  base_mainnet: {
    id: 'base_mainnet',
    name: 'Base',
    shortName: 'BASE',
    icon: 'base',
    color: '#0052FF',
    explorerUrl: 'https://basescan.org',
    explorerTxPath: '/tx/',
  },
  bsc_mainnet: {
    id: 'bsc_mainnet',
    name: 'BNB Chain',
    shortName: 'BNB',
    icon: 'bsc',
    color: '#F0B90B',
    explorerUrl: 'https://bscscan.com',
    explorerTxPath: '/tx/',
  },
  avalanche_mainnet: {
    id: 'avalanche_mainnet',
    name: 'Avalanche',
    shortName: 'AVAX',
    icon: 'avalanche',
    color: '#E84142',
    explorerUrl: 'https://snowtrace.io',
    explorerTxPath: '/tx/',
  },
  solana_mainnet: {
    id: 'solana_mainnet',
    name: 'Solana',
    shortName: 'SOL',
    icon: 'solana',
    color: '#14F195',
    explorerUrl: 'https://solscan.io',
    explorerTxPath: '/tx/',
  },
  solana_devnet: {
    id: 'solana_devnet',
    name: 'Solana Devnet',
    shortName: 'SOL',
    icon: 'solana',
    color: '#14F195',
    explorerUrl: 'https://solscan.io',
    explorerTxPath: '/tx/',
  },
  bitcoin_mainnet: {
    id: 'bitcoin_mainnet',
    name: 'Bitcoin',
    shortName: 'BTC',
    icon: 'bitcoin',
    color: '#F7931A',
    explorerUrl: 'https://blockstream.info',
    explorerTxPath: '/tx/',
  },
}

// Helper functions

/**
 * Get chain metadata with fallback for unknown chains
 */
export function getChainMetadata(chainId: string): ChainMetadata {
  return (
    CHAIN_METADATA[chainId] || {
      id: chainId,
      name: chainId.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      shortName: chainId.split('_')[0].toUpperCase().slice(0, 4),
      icon: 'default',
      color: '#6B7280',
      explorerUrl: '',
      explorerTxPath: '/tx/',
    }
  )
}

/**
 * Get explorer URL for a transaction
 */
export function getExplorerTxUrl(
  chainId: string,
  txHash: string
): string | null {
  const metadata = getChainMetadata(chainId)
  if (!metadata.explorerUrl) return null
  return `${metadata.explorerUrl}${metadata.explorerTxPath}${txHash}`
}

/**
 * Determine transaction direction from user's perspective
 */
export function getTransactionDirection(
  tx: NewsfeedTransaction
): TransactionDirection {
  if (tx.transaction_type === 'CONTRACT_CALL' || tx.transaction_type === 'CONTRACT_CREATE') {
    return 'contract'
  }
  return tx.is_sender ? 'sent' : 'received'
}

/**
 * Format transaction value for display
 */
export function formatTransactionValue(
  value: string | null,
  amountUsd: number | null
): string {
  if (amountUsd !== null && amountUsd > 0) {
    return `$${amountUsd.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`
  }
  if (value && value !== '0') {
    // For raw values, show abbreviated format
    const numValue = parseFloat(value)
    if (numValue >= 1e18) {
      return `${(numValue / 1e18).toFixed(4)} ETH`
    }
    return value
  }
  return '-'
}

/**
 * Truncate address for display
 */
export function truncateAddress(address: string, chars: number = 4): string {
  if (!address || address.length < chars * 2 + 2) return address
  return `${address.slice(0, chars + 2)}...${address.slice(-chars)}`
}
