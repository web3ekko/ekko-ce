/**
 * Transaction Newsfeed Component
 *
 * Displays real-time blockchain transactions for user's monitored wallets.
 * Uses the newsfeed API which queries DuckLake analytics for transactions
 * associated with addresses from the user's wallet alerts.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Text,
  Group,
  Stack,
  ThemeIcon,
  Badge,
  ActionIcon,
  ScrollArea,
  Box,
  Loader,
  Center,
  Card,
  Tooltip,
  Anchor,
  SegmentedControl,
} from '@mantine/core'
import {
  IconArrowUp,
  IconArrowDown,
  IconCode,
  IconRefresh,
  IconExternalLink,
  IconWallet,
  IconArrowsExchange,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { newsfeedApiService } from '../../services/newsfeed-api'
import { ChainLogo } from '../brand/ChainLogo'
import type {
  NewsfeedTransaction,
  NewsfeedResponse,
  TransactionDirection,
} from '../../types/newsfeed'
import {
  getChainMetadata,
  getExplorerTxUrl,
  getTransactionDirection,
  formatTransactionValue,
  truncateAddress,
} from '../../types/newsfeed'

// Time range filter options
type TimeRange = '1h' | '24h' | '7d' | 'all'

const TIME_RANGE_HOURS: Record<TimeRange, number | null> = {
  '1h': 1,
  '24h': 24,
  '7d': 168,
  all: null,
}

export function TransactionNewsfeed() {
  const [transactions, setTransactions] = useState<NewsfeedTransaction[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isAutoRefresh, setIsAutoRefresh] = useState(true)
  const [timeRange, setTimeRange] = useState<TimeRange>('24h')
  const [totalCount, setTotalCount] = useState(0)
  const [monitoredCount, setMonitoredCount] = useState(0)
  const [activeChains, setActiveChains] = useState<string[]>([])

  // Fetch transactions from API
  const fetchTransactions = useCallback(async () => {
    try {
      setError(null)
      const hours = TIME_RANGE_HOURS[timeRange]

      let response: NewsfeedResponse
      if (hours) {
        response = await newsfeedApiService.getRecentTransactions(hours, { limit: 50 })
      } else {
        response = await newsfeedApiService.getTransactions({ limit: 50 })
      }

      setTransactions(response.transactions)
      setTotalCount(response.total)
      setMonitoredCount(response.monitored_addresses)
      setActiveChains(response.chains)
    } catch (err: any) {
      console.error('Failed to fetch transaction newsfeed:', err)
      setError(err.message || 'Failed to load transactions')
    } finally {
      setIsLoading(false)
    }
  }, [timeRange])

  // Initial fetch
  useEffect(() => {
    fetchTransactions()
  }, [fetchTransactions])

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!isAutoRefresh) return

    const interval = setInterval(() => {
      fetchTransactions()
    }, 30000)

    return () => clearInterval(interval)
  }, [isAutoRefresh, fetchTransactions])

  // Get direction icon and color
  const getDirectionInfo = (direction: TransactionDirection) => {
    switch (direction) {
      case 'sent':
        return {
          icon: <IconArrowUp size={16} />,
          color: 'orange',
          label: 'Sent',
        }
      case 'received':
        return {
          icon: <IconArrowDown size={16} />,
          color: 'green',
          label: 'Received',
        }
      case 'contract':
        return {
          icon: <IconCode size={16} />,
          color: 'teal',
          label: 'Contract',
        }
    }
  }

  // Format timestamp for display
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60 * 1000) return 'Just now'
    if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / 3600000)}h ago`
    return date.toLocaleDateString()
  }

  // Get summary text for transaction
  const getSummary = (tx: NewsfeedTransaction): string => {
    if (tx.decoded_summary) return tx.decoded_summary
    if (tx.decoded_function_name) return `Called ${tx.decoded_function_name}()`

    const direction = getTransactionDirection(tx)
    if (direction === 'sent') {
      return `Sent to ${truncateAddress(tx.to_address || '', 6)}`
    }
    if (direction === 'received') {
      return `Received from ${truncateAddress(tx.from_address, 6)}`
    }
    return tx.transaction_type || 'Transaction'
  }

  return (
    <ExecutiveCard
      size="default"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      {/* Header */}
      <Group justify="space-between" mb="md">
        <Group gap="xs">
          <IconArrowsExchange size={20} color="#2563EB" />
          <Text fw={700} size="lg">
            Transactions
          </Text>
          {monitoredCount > 0 && (
            <Badge size="sm" variant="light" color="blue">
              {monitoredCount} wallets
            </Badge>
          )}
        </Group>

        <Group gap="xs">
          <SegmentedControl
            size="xs"
            value={timeRange}
            onChange={(value) => setTimeRange(value as TimeRange)}
            data={[
              { label: '1h', value: '1h' },
              { label: '24h', value: '24h' },
              { label: '7d', value: '7d' },
              { label: 'All', value: 'all' },
            ]}
          />
          <ActionIcon
            variant="subtle"
            size="sm"
            color={isAutoRefresh ? 'blue' : 'gray'}
            onClick={() => setIsAutoRefresh(!isAutoRefresh)}
            title={isAutoRefresh ? 'Live updates on' : 'Live updates off'}
          >
            <IconRefresh
              size={16}
              style={{
                animation: isAutoRefresh ? 'spin 4s linear infinite' : 'none',
              }}
            />
          </ActionIcon>
        </Group>
      </Group>

      {/* Content */}
      <ScrollArea h={400} offsetScrollbars type="hover">
        {isLoading ? (
          <Center h={200}>
            <Loader size="sm" />
          </Center>
        ) : error ? (
          <Center h={300}>
            <Stack align="center" gap="md">
              <Box p="xl" style={{ background: '#FEF2F2', borderRadius: '50%' }}>
                <IconArrowsExchange size={32} color="#DC2626" />
              </Box>
              <Text size="lg" fw={600} c="#0F172A">
                Failed to load
              </Text>
              <Text size="sm" c="dimmed" ta="center" maw={300}>
                {error}
              </Text>
              <ActionIcon
                variant="light"
                color="blue"
                onClick={() => {
                  setIsLoading(true)
                  fetchTransactions()
                }}
              >
                <IconRefresh size={16} />
              </ActionIcon>
            </Stack>
          </Center>
        ) : transactions.length === 0 ? (
          <Center h={300}>
            <Stack align="center" gap="md">
              <Box p="xl" style={{ background: '#F1F5F9', borderRadius: '50%' }}>
                <IconWallet size={32} color="#64748B" />
              </Box>
              <Text size="lg" fw={600} c="#0F172A">
                No transactions yet
              </Text>
              <Text size="sm" c="dimmed" ta="center" maw={300}>
                Transactions from your monitored wallets will appear here. Create
                a wallet alert to start tracking.
              </Text>
            </Stack>
          </Center>
        ) : (
          <Stack gap="sm">
            <AnimatePresence initial={false}>
              {transactions.map((tx, index) => {
                const direction = getTransactionDirection(tx)
                const directionInfo = getDirectionInfo(direction)
                const chainMeta = getChainMetadata(tx.chain_id)
                const explorerUrl = getExplorerTxUrl(tx.chain_id, tx.transaction_hash)

                return (
                  <motion.div
                    key={tx.transaction_hash}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: index * 0.03 }}
                  >
                    <Card
                      radius="md"
                      p="sm"
                      withBorder
                      style={{
                        borderColor: '#E6E9EE',
                        backgroundColor: '#FFFFFF',
                        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                      }}
                      styles={{
                        root: {
                          '&:hover': {
                            transform: 'translateY(-1px)',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                          },
                        },
                      }}
                    >
                      <Group align="flex-start" wrap="nowrap" gap="sm">
                        {/* Direction icon */}
                        <Tooltip label={directionInfo.label}>
                          <ThemeIcon
                            size="md"
                            radius="md"
                            variant="light"
                            color={directionInfo.color}
                          >
                            {directionInfo.icon}
                          </ThemeIcon>
                        </Tooltip>

                        {/* Main content */}
                        <Box style={{ flex: 1, minWidth: 0 }}>
                          <Group justify="space-between" align="center" mb={4}>
                            <Group gap="xs">
                              {/* Chain badge */}
                              <Badge
                                size="xs"
                                variant="dot"
                                style={{
                                  borderColor: chainMeta.color,
                                  '--badge-dot-color': chainMeta.color,
                                } as React.CSSProperties}
                                leftSection={<ChainLogo chain={chainMeta.icon} size="xs" />}
                              >
                                {chainMeta.shortName}
                              </Badge>

                              {/* Value if available */}
                              {(tx.amount_usd || tx.value) && (
                                <Text size="sm" fw={600} c="#0F172A">
                                  {formatTransactionValue(tx.value, tx.amount_usd)}
                                </Text>
                              )}
                            </Group>

                            <Group gap="xs">
                              {/* Timestamp */}
                              <Text size="xs" c="dimmed">
                                {formatTime(tx.block_timestamp)}
                              </Text>

                              {/* Explorer link */}
                              {explorerUrl && (
                                <Tooltip label="View on explorer">
                                  <Anchor
                                    href={explorerUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ lineHeight: 1 }}
                                  >
                                    <IconExternalLink size={14} color="#64748B" />
                                  </Anchor>
                                </Tooltip>
                              )}
                            </Group>
                          </Group>

                          {/* Summary */}
                          <Text size="sm" c="#475569" lineClamp={1}>
                            {getSummary(tx)}
                          </Text>

                          {/* Addresses */}
                          <Group gap="xs" mt={4}>
                            <Text size="xs" c="dimmed">
                              {tx.is_sender ? 'To:' : 'From:'}{' '}
                              <Text component="span" ff="monospace" size="xs">
                                {truncateAddress(
                                  tx.is_sender
                                    ? tx.to_address || ''
                                    : tx.from_address,
                                  6
                                )}
                              </Text>
                            </Text>

                            {/* Transaction type badge */}
                            {tx.transaction_subtype &&
                              tx.transaction_subtype !== 'unknown' && (
                                <Badge size="xs" variant="outline" color="gray">
                                  {tx.transaction_subtype.replace(/_/g, ' ')}
                                </Badge>
                              )}
                          </Group>
                        </Box>
                      </Group>
                    </Card>
                  </motion.div>
                )
              })}
            </AnimatePresence>

            {/* Load more indicator */}
            {totalCount > transactions.length && (
              <Center py="md">
                <Text size="xs" c="dimmed">
                  Showing {transactions.length} of {totalCount} transactions
                </Text>
              </Center>
            )}
          </Stack>
        )}
      </ScrollArea>

      {/* Footer stats */}
      {!isLoading && !error && transactions.length > 0 && (
        <Group justify="space-between" mt="md" pt="sm" style={{ borderTop: '1px solid #E6E9EE' }}>
          <Text size="xs" c="dimmed">
            {activeChains.length} chain{activeChains.length !== 1 ? 's' : ''} active
          </Text>
          <Badge
            size="xs"
            variant={isAutoRefresh ? 'dot' : 'outline'}
            color={isAutoRefresh ? 'green' : 'gray'}
          >
            {isAutoRefresh ? 'Live' : 'Paused'}
          </Badge>
        </Group>
      )}
    </ExecutiveCard>
  )
}
