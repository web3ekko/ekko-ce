import { Badge, Box } from '@mantine/core'
import {
  IconActivityHeartbeat,
  IconArrowsExchange,
  IconCoin,
  IconCrown,
  IconGasStation,
  IconNetwork,
  IconShield,
  IconReceipt,
  IconTrendingUp,
  IconTransferOut,
  IconWallet,
  IconPhoto,
} from '@tabler/icons-react'
import { getChainColor } from '../../utils/chain-identity'

type AlertEventBadgeProps = {
  eventType?: string | null
  subEvent?: string | null
  chain?: string | number | null
  size?: 'xs' | 'sm' | 'md'
}

type EventMeta = {
  label: string
  icon: typeof IconWallet
  color: string
}

const EVENT_CATALOG: Array<{ match: RegExp; meta: EventMeta }> = [
  { match: /swap/i, meta: { label: 'Swap', icon: IconArrowsExchange, color: '#0F766E' } },
  { match: /(transaction|tx)/i, meta: { label: 'Transaction', icon: IconReceipt, color: '#0F766E' } },
  { match: /(transfer|token_transfer)/i, meta: { label: 'Transfer', icon: IconTransferOut, color: '#2563EB' } },
  { match: /(balance|account)/i, meta: { label: 'Balance', icon: IconWallet, color: '#2563EB' } },
  { match: /(price|valuation|value)/i, meta: { label: 'Price', icon: IconTrendingUp, color: '#0EA5E9' } },
  { match: /(gas|fee|congestion)/i, meta: { label: 'Gas', icon: IconGasStation, color: '#EA580C' } },
  { match: /(security|alert|risk|suspicious)/i, meta: { label: 'Security', icon: IconShield, color: '#DC2626' } },
  { match: /(defi|liquidity|yield)/i, meta: { label: 'DeFi', icon: IconCoin, color: '#0891B2' } },
  { match: /(governance|vote)/i, meta: { label: 'Governance', icon: IconCrown, color: '#2563EB' } },
  { match: /(nft|mint|sale)/i, meta: { label: 'NFT', icon: IconPhoto, color: '#0EA5E9' } },
  { match: /(network|protocol)/i, meta: { label: 'Network', icon: IconNetwork, color: '#64748B' } },
]

const FALLBACK_META: EventMeta = {
  label: 'Alert',
  icon: IconActivityHeartbeat,
  color: '#475569',
}

function getEventMeta(eventType?: string | null, subEvent?: string | null): EventMeta {
  const candidates = [subEvent, eventType].filter(Boolean).join(' ')
  if (candidates) {
    for (const item of EVENT_CATALOG) {
      if (item.match.test(candidates)) {
        return item.meta
      }
    }
  }
  return FALLBACK_META
}

export function AlertEventBadge({ eventType, subEvent, chain, size = 'xs' }: AlertEventBadgeProps) {
  const meta = getEventMeta(eventType, subEvent)
  const baseColor = chain ? getChainColor(chain) : meta.color
  const Icon = meta.icon

  return (
    <Badge
      size={size}
      variant="light"
      styles={{
        root: {
          backgroundColor: `${baseColor}14`,
          color: baseColor,
          border: `1px solid ${baseColor}40`,
        },
      }}
      leftSection={
        <Box
          style={{
            width: 16,
            height: 16,
            borderRadius: 999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: `${baseColor}1F`,
            color: baseColor,
          }}
        >
          <Icon size={12} />
        </Box>
      }
    >
      {meta.label}
    </Badge>
  )
}

export default AlertEventBadge
