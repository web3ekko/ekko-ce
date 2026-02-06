export type ChainKey =
  | 'ethereum'
  | 'bitcoin'
  | 'solana'
  | 'avalanche'
  | 'polygon'
  | 'arbitrum'
  | 'optimism'
  | 'base'
  | 'bsc'

export type ChainIdentity = {
  key: ChainKey
  name: string
  symbol: string
  color: string
  logo: string
}

const CHAIN_ID_MAP: Record<number, ChainKey> = {
  1: 'ethereum',
  56: 'bsc',
  137: 'polygon',
  42161: 'arbitrum',
  43114: 'avalanche',
  8453: 'base',
}

const CHAIN_IDENTITIES: Record<ChainKey, ChainIdentity> = {
  ethereum: {
    key: 'ethereum',
    name: 'Ethereum',
    symbol: 'ETH',
    color: '#627EEA',
    logo: '/logos/chains/ethereum.png',
  },
  bitcoin: {
    key: 'bitcoin',
    name: 'Bitcoin',
    symbol: 'BTC',
    color: '#F7931A',
    logo: '/logos/chains/bitcoin.png',
  },
  solana: {
    key: 'solana',
    name: 'Solana',
    symbol: 'SOL',
    color: '#00FFA3',
    logo: '/logos/chains/solana.svg',
  },
  avalanche: {
    key: 'avalanche',
    name: 'Avalanche',
    symbol: 'AVAX',
    color: '#E84142',
    logo: '/logos/chains/avalanche.svg',
  },
  polygon: {
    key: 'polygon',
    name: 'Polygon',
    symbol: 'MATIC',
    color: '#8247E5',
    logo: '/logos/chains/polygon.svg',
  },
  arbitrum: {
    key: 'arbitrum',
    name: 'Arbitrum',
    symbol: 'ARB',
    color: '#28A0F0',
    logo: '/logos/chains/arbitrum.svg',
  },
  optimism: {
    key: 'optimism',
    name: 'Optimism',
    symbol: 'OP',
    color: '#FF0420',
    logo: '/logos/chains/optimism.svg',
  },
  base: {
    key: 'base',
    name: 'Base',
    symbol: 'BASE',
    color: '#0052FF',
    logo: '/logos/chains/base.svg',
  },
  bsc: {
    key: 'bsc',
    name: 'BNB Chain',
    symbol: 'BNB',
    color: '#F0B90B',
    logo: '/logos/chains/bsc.png',
  },
}

const NETWORK_SYMBOL_MAP: Record<string, ChainKey> = {
  ETH: 'ethereum',
  BTC: 'bitcoin',
  SOL: 'solana',
  AVAX: 'avalanche',
  MATIC: 'polygon',
  ARB: 'arbitrum',
  OP: 'optimism',
  BASE: 'base',
  BNB: 'bsc',
}

const CHAIN_ALIASES: Array<{ key: ChainKey; match: RegExp }> = [
  { key: 'ethereum', match: /(ethereum|^eth$|^eth_|^eth-)/ },
  { key: 'bitcoin', match: /(bitcoin|^btc$|^btc_|^btc-)/ },
  { key: 'solana', match: /(solana|^sol$|^sol_)/ },
  { key: 'avalanche', match: /(avalanche|avax)/ },
  { key: 'polygon', match: /(polygon|matic)/ },
  { key: 'arbitrum', match: /(arbitrum|^arb$|^arb_)/ },
  { key: 'optimism', match: /(optimism|^op$|^op_)/ },
  { key: 'base', match: /(base)/ },
  { key: 'bsc', match: /(bsc|binance|bnb)/ },
]

export function normalizeChainKey(input?: string | number | null): ChainKey | null {
  if (input === null || input === undefined) return null
  if (typeof input === 'number') {
    return CHAIN_ID_MAP[input] || null
  }

  const raw = input.toString().trim()
  if (!raw) return null

  const numeric = Number(raw)
  if (!Number.isNaN(numeric) && CHAIN_ID_MAP[numeric]) {
    return CHAIN_ID_MAP[numeric]
  }

  const cleaned = raw.toLowerCase()
  if (raw.includes(':')) {
    const network = raw.split(':')[0]?.trim().toUpperCase()
    if (network && NETWORK_SYMBOL_MAP[network]) {
      return NETWORK_SYMBOL_MAP[network]
    }
  }
  for (const alias of CHAIN_ALIASES) {
    if (alias.match.test(cleaned)) {
      return alias.key
    }
  }

  return null
}

export function getChainIdentity(input?: string | number | null): ChainIdentity | null {
  const key = normalizeChainKey(input)
  if (!key) return null
  return CHAIN_IDENTITIES[key]
}

export function getChainLogoPath(input?: string | number | null): string | null {
  const identity = getChainIdentity(input)
  return identity ? identity.logo : null
}

export function getChainColor(input?: string | number | null): string {
  const identity = getChainIdentity(input)
  return identity?.color || '#64748B'
}

export function getChainSymbol(input?: string | number | null): string {
  const identity = getChainIdentity(input)
  return identity?.symbol || 'CHAIN'
}

export function buildNetworkKey(input?: string | number | null, subnet: string = 'mainnet'): string {
  const symbol = getChainSymbol(input).toUpperCase()
  return `${symbol}:${subnet.toLowerCase()}`
}

export function buildTargetKey(
  input: string | number | null,
  address: string,
  subnet: string = 'mainnet'
): string {
  const symbol = getChainSymbol(input).toUpperCase()
  return `${symbol}:${subnet.toLowerCase()}:${address}`
}
