import { Box, Text } from '@mantine/core'
import { TokenIcon } from '@web3icons/react/dynamic'

type TokenLogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number

const SIZE_MAP: Record<Exclude<TokenLogoSize, number>, number> = {
  xs: 16,
  sm: 20,
  md: 28,
  lg: 36,
  xl: 48,
}

export interface TokenLogoProps {
  symbol?: string
  name?: string
  address?: string
  network?: string
  size?: TokenLogoSize
  label?: string
  radius?: number
  variant?: 'mono' | 'branded' | 'background'
}

export function TokenLogo({
  symbol,
  name,
  address,
  network,
  size = 'sm',
  label,
  radius,
  variant = 'branded',
}: TokenLogoProps) {
  const numericSize = typeof size === 'number' ? size : SIZE_MAP[size]
  const fallbackLabel = (label || symbol || name || 'TK').slice(0, 2).toUpperCase()
  const displayName = label || symbol || name || 'Token'
  const borderRadius = radius ?? Math.max(6, Math.round(numericSize / 4))
  const iconPadding = Math.max(2, Math.round(numericSize * 0.12))
  const iconSize = Math.max(12, numericSize - iconPadding * 2)

  const iconProps = symbol
    ? { symbol }
    : address && network
      ? { address, network }
      : name
        ? { name }
        : null

  if (!iconProps) {
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
          {fallbackLabel}
        </Text>
      </Box>
    )
  }

  return (
    <Box
      role="img"
      aria-label={`${displayName} token logo`}
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
      <TokenIcon
        {...iconProps}
        size={iconSize}
        variant={variant}
        fallback={
          <Text size={Math.max(10, Math.round(numericSize / 2.5))} fw={700} c="#475569">
            {fallbackLabel}
          </Text>
        }
        aria-hidden="true"
        focusable="false"
      />
    </Box>
  )
}

export default TokenLogo
