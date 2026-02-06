/**
 * Chain Monitoring Widgets - Simplified Version
 *
 * Displays health status and key metrics for blockchain networks in a clean, intuitive layout
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Text,
  Group,
  Badge,
  Stack,
  Box,
  Progress,
  SimpleGrid,
  Button,
  Modal,
  Card,
  Tabs,
  Loader,
  Center,
} from '@mantine/core'
import { IconActivity, IconUsers, IconTrendingUp, IconAlertCircle, IconCheck, IconClock } from '@tabler/icons-react'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { ChainLogo } from '../brand/ChainLogo'
import { dashboardApiService, type ChainStats } from '../../services/dashboard-api'
import { getChainColor, normalizeChainKey } from '../../utils/chain-identity'

interface ChainData {
  id: string
  name: string
  health: number
  tps: number | null
  activeWallets: number
  avgBlockTime?: string
  status: 'operational' | 'degraded' | 'down'
  color: string
  type: 'L1' | 'L2' | 'Alt'
  change24h?: number
  // From API
  alerts?: {
    total: number
    active: number
    inactive: number
  }
}

// Chain type mapping
const CHAIN_TYPES: Record<string, 'L1' | 'L2' | 'Alt'> = {
  ethereum: 'L1',
  bitcoin: 'L1',
  solana: 'Alt',
  polygon: 'L2',
  arbitrum: 'L2',
  optimism: 'L2',
  base: 'L2',
  avalanche: 'L1',
}

// Map API chain stats to display format
function mapChainStatsToData(stats: ChainStats): ChainData {
  const normalizedKey = normalizeChainKey(stats.chain)
  const chainId = normalizedKey || stats.chain.toLowerCase().replace(/[^a-z]/g, '')
  const activeRatio = stats.alerts.total > 0 ? (stats.alerts.active / stats.alerts.total) * 100 : 100

  return {
    id: chainId,
    name: stats.chain,
    health: Math.round(activeRatio),
    tps: null,
    activeWallets: stats.alerts.active,
    avgBlockTime: undefined,
    status: activeRatio >= 90 ? 'operational' : activeRatio >= 50 ? 'degraded' : 'down',
    color: getChainColor(normalizedKey || stats.chain),
    type: CHAIN_TYPES[chainId] || 'L1',
    change24h: undefined,
    alerts: stats.alerts,
  }
}

export function ChainMonitoringWidgets() {
  const [chains, setChains] = useState<ChainData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [detailsOpened, setDetailsOpened] = useState(false)
  const [selectedChain, setSelectedChain] = useState<ChainData | null>(null)

  // Fetch chain stats from API
  const fetchChainStats = useCallback(async () => {
    try {
      const response = await dashboardApiService.getChainStats()
      const mappedChains = response.chains.map(mapChainStatsToData)
      setChains(mappedChains)
    } catch (error) {
      console.error('Failed to fetch chain stats:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchChainStats()
  }, [fetchChainStats])

  const statusColor = (status: ChainData['status']) => {
    if (status === 'operational') return 'green'
    if (status === 'degraded') return 'orange'
    return 'red'
  }

  const statusIcon = (status: ChainData['status']) => {
    if (status === 'operational') return <IconCheck size={14} />
    if (status === 'degraded') return <IconAlertCircle size={14} />
    return <IconAlertCircle size={14} />
  }

  const handleViewDetails = (chain: ChainData) => {
    setSelectedChain(chain)
    setDetailsOpened(true)
  }

  // Show top 6 chains
  const displayChains = chains.slice(0, 6)
  const operationalCount = chains.filter(c => c.status === 'operational').length

  return (
    <>
      <ExecutiveCard variant="glass" glowOnHover size="compact">
        <Stack gap="sm">
          {/* Header with Summary Stats - denser */}
          <Group justify="space-between" align="center">
            <div>
              <Text fw={700} size="md" c="#0F172A">Network Status</Text>
              <Text size="xs" c="#64748B">
                {operationalCount}/{chains.length} operational
              </Text>
            </div>
            <Badge
              size="sm"
              color="green"
              variant="light"
              leftSection={<IconCheck size={12} />}
            >
              Normal
            </Badge>
          </Group>

          {/* Network Grid - Compact Cards */}
          {isLoading ? (
            <Center py="xl">
              <Loader size="sm" />
            </Center>
          ) : chains.length === 0 ? (
            <Center py="xl" flex={1}>
              <Stack align="center" gap="xs">
                <Box p="md" style={{ background: '#F1F5F9', borderRadius: '50%' }}>
                  <IconActivity size={24} color="#64748B" />
                </Box>
                <Text size="sm" fw={500} c="#0F172A">No networks monitored yet</Text>
                <Text size="xs" c="dimmed" ta="center" maw={220}>
                  Blockchain status and metrics will appear here once monitoring is active.
                </Text>
              </Stack>
            </Center>
          ) : (
            <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} spacing="xs">
              {displayChains.map((chain) => (
                <Card
                  key={chain.id}
                  padding="xs"
                  radius="md"
                  withBorder
                  style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between'
                  }}
                  onClick={() => handleViewDetails(chain)}
                  styles={{
                    root: {
                      '&:hover': {
                        borderColor: chain.color,
                        boxShadow: `0 4px 12px ${chain.color}15`,
                        transform: 'translateY(-2px)',
                      }
                    }
                  }}
                >
                  <Stack gap={8} h="100%">
                    {/* Chain Name with logo */}
                    <Stack gap={6} align="center" style={{ flex: 1, justifyContent: 'center' }}>
                      <ChainLogo chain={chain.id} size="sm" />
                      <Text
                        fw={700}
                        size="sm"
                        c="#0F172A"
                        ta="center"
                        lh={1.2}
                        tt="capitalize"
                      >
                        {chain.name}
                      </Text>
                    </Stack>

                    {/* Compact Metrics Row */}
                    <Group gap={4} justify="center" style={{ borderTop: '1px solid #F1F5F9', paddingTop: 8 }}>
                      <Badge
                        size="xs"
                        variant="dot"
                        color={statusColor(chain.status)}
                        styles={{ root: { paddingLeft: 0, paddingRight: 0, background: 'transparent' } }}
                      >
                        {chain.health}%
                      </Badge>
                    </Group>

                    {/* Health Bar */}
                    <Progress
                      value={chain.health}
                      color={statusColor(chain.status)}
                      size="sm"
                      radius="lg"
                      style={{ height: 6 }}
                    />
                  </Stack>
                </Card>
              ))}
            </SimpleGrid>
          )}

          {/* View All Link - compact */}
          <Button
            variant="subtle"
            color="blue"
            size="xs"
            onClick={() => {
              setSelectedChain(null)
              setDetailsOpened(true)
            }}
            style={{ alignSelf: 'flex-end' }}
          >
            View all networks →
          </Button>
        </Stack>
      </ExecutiveCard >

      {/* Details Modal */}
      < Modal
        opened={detailsOpened}
        onClose={() => setDetailsOpened(false)
        }
        title={selectedChain ? `${selectedChain.name} Details` : "All Networks"}
        size="lg"
      >
        {
          selectedChain ? (
            // Single chain details
            <Stack gap="md" >
              <Group justify="space-between">
                <Badge
                  size="lg"
                  color={statusColor(selectedChain.status)}
                  variant="light"
                  leftSection={statusIcon(selectedChain.status)}
                >
                  {selectedChain.status}
                </Badge>
                <Badge size="lg" variant="outline">
                  {selectedChain.type}
                </Badge>
              </Group>

              <SimpleGrid cols={2} spacing="md">
                <Card padding="md" radius="md" withBorder>
                  <Stack gap="xs">
                    <Group gap="xs">
                      <IconActivity size={16} color="#64748B" />
                      <Text size="sm" c="#64748B">Network Health</Text>
                    </Group>
                    <Text size="xl" fw={700} c="#0F172A">{selectedChain.health}%</Text>
                    <Progress value={selectedChain.health} color={statusColor(selectedChain.status)} />
                  </Stack>
                </Card>

                <Card padding="md" radius="md" withBorder>
                  <Stack gap="xs">
                    <Group gap="xs">
                      <IconTrendingUp size={16} color="#64748B" />
                      <Text size="sm" c="#64748B">Transactions/Sec</Text>
                    </Group>
                    <Text size="xl" fw={700} c="#0F172A">
                      {selectedChain.tps === null
                        ? 'N/A'
                        : selectedChain.tps >= 1000
                          ? `${(selectedChain.tps / 1000).toFixed(1)}K`
                          : selectedChain.tps}
                    </Text>
                  </Stack>
                </Card>

                <Card padding="md" radius="md" withBorder>
                  <Stack gap="xs">
                    <Group gap="xs">
                      <IconUsers size={16} color="#64748B" />
                      <Text size="sm" c="#64748B">Active Wallets</Text>
                    </Group>
                    <Text size="xl" fw={700} c="#0F172A">
                      {selectedChain.activeWallets.toLocaleString()}
                    </Text>
                  </Stack>
                </Card>

                <Card padding="md" radius="md" withBorder>
                  <Stack gap="xs">
                    <Group gap="xs">
                      <IconClock size={16} color="#64748B" />
                      <Text size="sm" c="#64748B">Avg Block Time</Text>
                    </Group>
                    <Text size="xl" fw={700} c="#0F172A">{selectedChain.avgBlockTime || 'N/A'}</Text>
                  </Stack>
                </Card>
              </SimpleGrid>
            </Stack>
          ) : (
            // All networks list
            <Tabs defaultValue="all">
              <Tabs.List>
                <Tabs.Tab value="all">All Networks</Tabs.Tab>
                <Tabs.Tab value="l1">Layer 1</Tabs.Tab>
                <Tabs.Tab value="l2">Layer 2</Tabs.Tab>
                <Tabs.Tab value="alt">Alternative</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="all" pt="md">
                <Stack gap="sm">
                  {chains.map((chain) => (
                    <Card
                      key={chain.id}
                      padding="md"
                      radius="md"
                      withBorder
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleViewDetails(chain)}
                    >
                      <Group justify="space-between">
                        <Group gap="md">
                          <ChainLogo chain={chain.id} size="sm" />
                          <div>
                            <Text fw={600} c="#0F172A">{chain.name}</Text>
                            <Text size="xs" c="#64748B">
                              {chain.tps === null ? 'TPS N/A' : `${chain.tps} TPS`} • {chain.avgBlockTime || 'Block time N/A'}
                            </Text>
                          </div>
                        </Group>
                        <Group gap="md">
                          <Badge size="sm" color={statusColor(chain.status)} variant="light">
                            {chain.health}% health
                          </Badge>
                          <Badge size="sm" variant="outline">{chain.type}</Badge>
                        </Group>
                      </Group>
                    </Card>
                  ))}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="l1" pt="md">
                <Stack gap="sm">
                  {chains.filter(c => c.type === 'L1').map((chain) => (
                    <Card key={chain.id} padding="md" radius="md" withBorder onClick={() => handleViewDetails(chain)}>
                      <Text fw={600}>{chain.name}</Text>
                    </Card>
                  ))}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="l2" pt="md">
                <Stack gap="sm">
                  {chains.filter(c => c.type === 'L2').map((chain) => (
                    <Card key={chain.id} padding="md" radius="md" withBorder onClick={() => handleViewDetails(chain)}>
                      <Text fw={600}>{chain.name}</Text>
                    </Card>
                  ))}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="alt" pt="md">
                <Stack gap="sm">
                  {chains.filter(c => c.type === 'Alt').map((chain) => (
                    <Card key={chain.id} padding="md" radius="md" withBorder onClick={() => handleViewDetails(chain)}>
                      <Text fw={600}>{chain.name}</Text>
                    </Card>
                  ))}
                </Stack>
              </Tabs.Panel>
            </Tabs>
          )}
      </Modal >
    </>
  )
}
