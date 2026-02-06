/**
 * Real-time Understanding Panel
 * 
 * Shows parsed query components with confidence indicators
 */

import { Card, Stack, Group, Text, Badge, ThemeIcon, Box, Tooltip } from '@mantine/core'
import {
  IconCheck,
  IconQuestionMark,
  IconAlertCircle,
  IconBrain,
  IconLink,
  IconWallet,
  IconTrendingUp,
} from '@tabler/icons-react'
import { motion } from 'framer-motion'
import type { ParsedCondition, ThresholdValue } from './CreateAlertOptimized'
import { ChainLogo } from '../brand/ChainLogo'

interface RealtimeUnderstandingPanelProps {
  understanding: {
    eventType?: string
    subEvent?: string
    conditions?: ParsedCondition[]
    chains?: string[]
    wallets?: string[]
    thresholds?: ThresholdValue[]
  }
  confidence: number
}

// NLP event type labels (from Gemini classification)
const eventTypeLabels: Record<string, string> = {
  // NLP API event types (uppercase)
  'ACCOUNT_EVENT': 'Account Event',
  'ASSET_EVENT': 'Asset Event',
  'CONTRACT_INTERACTION': 'Contract Interaction',
  'DEFI_EVENT': 'DeFi Event',
  'GOVERNANCE': 'Governance',
  'NFT_EVENT': 'NFT Event',
  'NETWORK_EVENT': 'Network Event',
  'CUSTOM': 'Custom Event',
  // Legacy local event types (lowercase)
  balance_change: 'Balance Changes',
  balance_threshold: 'Balance Threshold',
  transaction: 'Transactions',
  transfer: 'Transfer',
  swap: 'Swap',
  gas_price: 'Gas Price',
  liquidity: 'Liquidity',
  nft: 'NFT',
  custom: 'Custom Event',
}

// Sub-event labels for human-readable display
const subEventLabels: Record<string, string> = {
  'BALANCE_THRESHOLD': 'Balance Threshold',
  'BALANCE_CHANGE': 'Balance Change',
  'TOKEN_TRANSFER': 'Token Transfer',
  'PRICE_THRESHOLD': 'Price Threshold',
  'PRICE_CHANGE': 'Price Change',
  'SWAP': 'Swap',
  'LIQUIDITY_ADD': 'Add Liquidity',
  'LIQUIDITY_REMOVE': 'Remove Liquidity',
  'LIQUIDATION_RISK': 'Liquidation Risk',
  'YIELD_CHANGE': 'Yield Change',
  'PROPOSAL_CREATED': 'Proposal Created',
  'VOTE_CAST': 'Vote Cast',
  'MINT': 'Mint',
  'TRANSFER': 'Transfer',
  'SALE': 'Sale',
  'GAS_SPIKE': 'Gas Spike',
  'CONGESTION': 'Network Congestion',
  'USER_DEFINED': 'User Defined',
  'CUSTOM': 'Custom',
}

export function RealtimeUnderstandingPanel({
  understanding,
  confidence
}: RealtimeUnderstandingPanelProps) {
  const { eventType, subEvent, conditions, chains, wallets, thresholds } = understanding

  const getConfidenceIcon = (itemConfidence: number) => {
    if (itemConfidence >= 80) return <IconCheck size={16} />
    if (itemConfidence >= 50) return <IconQuestionMark size={16} />
    return <IconAlertCircle size={16} />
  }

  const getConfidenceColor = (itemConfidence: number) => {
    if (itemConfidence >= 80) return 'green'
    if (itemConfidence >= 50) return 'yellow'
    return 'red'
  }

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 },
  }

  return (
    <Card radius="md" p="lg" withBorder>
      <Stack gap="md">
        <Group justify="space-between">
          <Group gap="xs">
            <ThemeIcon size="sm" radius="xl" variant="light" color="blue">
              <IconBrain size={16} />
            </ThemeIcon>
            <Text size="sm" fw={600}>Real-time Understanding</Text>
          </Group>
          <Badge 
            size="sm" 
            variant="light" 
            color={confidence >= 80 ? 'green' : confidence >= 50 ? 'yellow' : 'red'}
          >
            {confidence}% Confidence
          </Badge>
        </Group>

        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
        >
          <Stack gap="sm">
            {/* Event Type */}
            {eventType && (
              <motion.div variants={item}>
                <UnderstandingCard
                  icon={<IconTrendingUp size={16} />}
                  label="Event Type"
                  value={
                    <Group gap="xs">
                      <Badge size="sm" color="blue" variant="light">
                        {eventTypeLabels[eventType] || eventType}
                      </Badge>
                      {subEvent && subEvent !== eventType && (
                        <Badge size="sm" color="gray" variant="outline">
                          {subEventLabels[subEvent] || subEvent}
                        </Badge>
                      )}
                    </Group>
                  }
                  confidence={eventType !== 'custom' && eventType !== 'CUSTOM' ? 90 : 50}
                />
              </motion.div>
            )}

            {/* Chains */}
            {chains && chains.length > 0 && (
              <motion.div variants={item}>
                <UnderstandingCard
                  icon={<IconLink size={16} />}
                  label="Blockchain Networks"
                  value={
                    <Group gap={4}>
                      {chains.map(chain => (
                        <Badge
                          key={chain}
                          size="sm"
                          radius="sm"
                          leftSection={<ChainLogo chain={chain} size="sm" />}
                        >
                          {chain}
                        </Badge>
                      ))}
                    </Group>
                  }
                  confidence={85}
                />
              </motion.div>
            )}

            {/* Conditions */}
            {conditions && conditions.length > 0 && (
              <motion.div variants={item}>
                <UnderstandingCard
                  icon={<IconAlertCircle size={16} />}
                  label="Conditions"
                  value={conditions.map(cond => (
                    <Text key={`${cond.field}-${cond.operator}`} size="sm">
                      {cond.field} {cond.operator} {cond.value} {cond.unit}
                    </Text>
                  ))}
                  confidence={80}
                />
              </motion.div>
            )}

            {/* Wallets */}
            {wallets && wallets.length > 0 && (
              <motion.div variants={item}>
                <UnderstandingCard
                  icon={<IconWallet size={16} />}
                  label="Specific Wallets"
                  value={wallets.map(wallet => (
                    <Badge key={wallet} size="xs" variant="outline">
                      {wallet.slice(0, 6)}...{wallet.slice(-4)}
                    </Badge>
                  ))}
                  confidence={95}
                />
              </motion.div>
            )}

            {/* Missing Information */}
            {(!eventType || !conditions || conditions.length === 0) && (
              <motion.div variants={item}>
                <Card p="xs" radius="sm" withBorder style={{ borderStyle: 'dashed' }}>
                  <Group gap="xs">
                    <ThemeIcon size="sm" radius="xl" variant="light" color="orange">
                      <IconQuestionMark size={14} />
                    </ThemeIcon>
                    <Text size="xs" c="dimmed">
                      {!eventType && "Specify what event to monitor"}
                      {eventType && (!conditions || conditions.length === 0) && "Add specific conditions"}
                    </Text>
                  </Group>
                </Card>
              </motion.div>
            )}
          </Stack>
        </motion.div>
      </Stack>
    </Card>
  )
}

interface UnderstandingCardProps {
  icon: React.ReactNode
  label: string
  value: React.ReactNode
  confidence: number
}

function UnderstandingCard({ icon, label, value, confidence }: UnderstandingCardProps) {
  const confidenceColor = confidence >= 80 ? 'green' : confidence >= 50 ? 'yellow' : 'red'
  
  return (
    <Card p="sm" radius="sm" withBorder>
      <Group justify="space-between" style={{ flexWrap: 'nowrap' }}>
        <Group gap="xs" style={{ flex: 1, flexWrap: 'nowrap' }}>
          <ThemeIcon size="sm" radius="xl" variant="light" color="gray">
            {icon}
          </ThemeIcon>
          <Box style={{ flex: 1 }}>
            <Text size="xs" c="dimmed" fw={500}>{label}</Text>
            <Box mt={2}>
              {typeof value === 'string' ? (
                <Text size="sm" fw={600}>{value}</Text>
              ) : (
                value
              )}
            </Box>
          </Box>
        </Group>
        
        <Tooltip label={`${confidence}% confidence`}>
          <ThemeIcon 
            size="xs" 
            radius="xl" 
            variant="light" 
            color={confidenceColor}
          >
            {confidence >= 80 ? <IconCheck size={12} /> : 
             confidence >= 50 ? <IconQuestionMark size={12} /> : 
             <IconAlertCircle size={12} />}
          </ThemeIcon>
        </Tooltip>
      </Group>
    </Card>
  )
}
