import { Box, Text } from '@mantine/core'
import { WalletIcon } from '@web3icons/react/dynamic'

type WalletLogoSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number

const SIZE_MAP: Record<Exclude<WalletLogoSize, number>, number> = {
  xs: 16,
  sm: 20,
  md: 28,
  lg: 36,
  xl: 48,
}

export interface WalletLogoProps {
  name?: string
  id?: string
  size?: WalletLogoSize
  label?: string
  radius?: number
  variant?: 'mono' | 'branded' | 'background'
}

export function WalletLogo({
  name,
  id,
  size = 'sm',
  label,
  radius,
  variant = 'branded',
}: WalletLogoProps) {
  const numericSize = typeof size === 'number' ? size : SIZE_MAP[size]
  const fallbackLabel = (label || name || id || 'WL').slice(0, 2).toUpperCase()
  const displayName = label || name || id || 'Wallet'
  const borderRadius = radius ?? Math.max(6, Math.round(numericSize / 4))
  const iconPadding = Math.max(2, Math.round(numericSize * 0.12))
  const iconSize = Math.max(12, numericSize - iconPadding * 2)

  const iconProps = name ? { name } : id ? { id } : null

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
      aria-label={`${displayName} wallet logo`}
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
      <WalletIcon
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

export default WalletLogo
