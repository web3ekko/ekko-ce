import { Box, Text } from '@mantine/core'
import type { IconComponent } from '@web3icons/react'
import NetworkArbitrumOne from '@web3icons/react/icons/networks/NetworkArbitrumOne'
import NetworkAvalanche from '@web3icons/react/icons/networks/NetworkAvalanche'
import NetworkBase from '@web3icons/react/icons/networks/NetworkBase'
import NetworkBinanceSmartChain from '@web3icons/react/icons/networks/NetworkBinanceSmartChain'
import NetworkBitcoin from '@web3icons/react/icons/networks/NetworkBitcoin'
import NetworkEthereum from '@web3icons/react/icons/networks/NetworkEthereum'
import NetworkOptimism from '@web3icons/react/icons/networks/NetworkOptimism'
import NetworkPolygon from '@web3icons/react/icons/networks/NetworkPolygon'
import NetworkSolana from '@web3icons/react/icons/networks/NetworkSolana'
import { getChainIdentity, getChainSymbol, normalizeChainKey } from '../../utils/chain-identity'
import type { ChainKey } from '../../utils/chain-identity'

type ChainLogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number

const SIZE_MAP: Record<Exclude<ChainLogoSize, number>, number> = {
  xs: 16,
  sm: 20,
  md: 28,
  lg: 36,
  xl: 48,
}

export interface ChainLogoProps {
  chain?: string | number | null
  size?: ChainLogoSize
  label?: string
  radius?: number
}

const NETWORK_ICON_MAP: Partial<Record<ChainKey, IconComponent>> = {
  ethereum: NetworkEthereum,
  bitcoin: NetworkBitcoin,
  solana: NetworkSolana,
  avalanche: NetworkAvalanche,
  polygon: NetworkPolygon,
  arbitrum: NetworkArbitrumOne,
  optimism: NetworkOptimism,
  base: NetworkBase,
  bsc: NetworkBinanceSmartChain,
}

export function ChainLogo({ chain, size = 'sm', label, radius }: ChainLogoProps) {
  const identity = getChainIdentity(chain)
  const chainKey = normalizeChainKey(chain)
  const numericSize = typeof size === 'number' ? size : SIZE_MAP[size]
  const fallbackLabel = label || getChainSymbol(chain)
  const borderRadius = radius ?? Math.max(6, Math.round(numericSize / 4))
  const iconPadding = Math.max(2, Math.round(numericSize * 0.12))
  const iconSize = Math.max(12, numericSize - iconPadding * 2)

  if (!identity) {
    return (
      <Box
        style={{
          width: numericSize,
          height: numericSize,
          borderRadius,
          backgroundColor: '#E2E8F0',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Text size={Math.max(10, Math.round(numericSize / 2.5))} fw={700} c="#475569">
          {fallbackLabel.slice(0, 2).toUpperCase()}
        </Text>
      </Box>
    )
  }

  const NetworkIcon = chainKey ? NETWORK_ICON_MAP[chainKey] : null

  if (NetworkIcon) {
    return (
      <Box
        role="img"
        aria-label={`${identity.name} logo`}
        style={{
          width: numericSize,
          height: numericSize,
          borderRadius,
          backgroundColor: '#FFFFFF',
          border: '1px solid #E6E9EE',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxSizing: 'border-box',
        }}
      >
        <NetworkIcon size={iconSize} variant="branded" aria-hidden="true" focusable="false" />
      </Box>
    )
  }

  return (
    <Box
      component="img"
      src={identity.logo}
      alt={`${identity.name} logo`}
      style={{
        width: numericSize,
        height: numericSize,
        borderRadius,
        objectFit: 'contain',
        backgroundColor: '#FFFFFF',
        border: '1px solid #E6E9EE',
      }}
    />
  )
}

export default ChainLogo
