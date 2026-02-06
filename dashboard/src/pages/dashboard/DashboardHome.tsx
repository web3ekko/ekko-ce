/**
 * Dashboard Home Page Component
 */

import { useEffect, useMemo, useState } from 'react'
import { Title, Text, Stack, Card, Grid, Group, Badge, Center, Loader } from '@mantine/core'
import { IconBell, IconShield, IconActivity, IconSparkles, IconCheck } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useAuthStore } from '../../store/auth'
import { dashboardApiService, type ChainStatsResponse } from '../../services/dashboard-api'
import { useDashboardStats } from '../../hooks/useDashboardStats'

export function DashboardHome() {
  const { user } = useAuthStore()
  const [chainSummary, setChainSummary] = useState<ChainStatsResponse['summary'] | null>(null)
  const [activityCount, setActivityCount] = useState(0)
  const [isDashboardLoading, setIsDashboardLoading] = useState(true)
  const { stats, isLoading: isStatsLoading } = useDashboardStats()
  const isLoading = isDashboardLoading || isStatsLoading

  useEffect(() => {
    const showWelcome = localStorage.getItem('showWelcomeMessage')
    if (showWelcome === 'true') {
      notifications.show({
        title: 'Welcome to Ekko! 🎉',
        message: 'Your account has been created successfully. Start by setting up your first blockchain monitoring alert.',
        color: 'teal',
        icon: <IconSparkles size={20} />,
        autoClose: 8000,
      })
      localStorage.removeItem('showWelcomeMessage')
    }
  }, [])

  useEffect(() => {
    let isActive = true

    const loadStats = async () => {
      setIsDashboardLoading(true)
      try {
        const [chainResponse, activityResponse] = await Promise.all([
          dashboardApiService.getChainStats(),
          dashboardApiService.getActivity({ limit: 1 }),
        ])

        if (!isActive) return
        setChainSummary(chainResponse.summary)
        setActivityCount(activityResponse.total)
      } catch (error) {
        console.error('Failed to load dashboard stats:', error)
      } finally {
        if (isActive) {
          setIsDashboardLoading(false)
        }
      }
    }

    loadStats()

    return () => {
      isActive = false
    }
  }, [])

  const gettingStartedItems = useMemo(() => {
    const walletCount = stats?.wallets.total ?? 0
    const alertsCount = stats?.alerts.total ?? 0
    const chainsCount = chainSummary?.total_chains ?? 0

    return [
      { label: 'Add your first wallet', done: walletCount > 0 },
      { label: 'Create your first alert', done: alertsCount > 0 },
      { label: 'Activate monitoring on a chain', done: chainsCount > 0 },
    ]
  }, [chainSummary?.total_chains, stats?.alerts.total, stats?.wallets.total])

  const isChecklistComplete = gettingStartedItems.every((item) => item.done)

  return (
    <Stack gap="xl">
      <div>
        <Title order={1}>Welcome back, {user?.email}!</Title>
        <Text c="dimmed" size="lg">
          Here's what's happening with your blockchain monitoring
        </Text>
      </div>

      {isLoading ? (
        <Center h={200}>
          <Loader size="lg" />
        </Center>
      ) : (
        <Grid>
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card shadow="sm" padding="lg" radius="md" withBorder>
              <Group justify="space-between" mb="xs">
                <Text fw={500}>Active Alerts</Text>
                <IconBell size="1.2rem" />
              </Group>
              <Text size="xl" fw={700} c="blue">
                {stats?.alerts.active ?? 0}
              </Text>
              <Text size="sm" c="dimmed">
                {stats?.alerts.total ? `${stats.alerts.total} total alerts` : 'No alerts yet'}
              </Text>
            </Card>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card shadow="sm" padding="lg" radius="md" withBorder>
              <Group justify="space-between" mb="xs">
                <Text fw={500}>Monitored Chains</Text>
                <IconShield size="1.2rem" />
              </Group>
              <Text size="xl" fw={700} c="green">
                {chainSummary?.total_chains ?? 0}
              </Text>
              <Text size="sm" c="dimmed">
                {chainSummary?.total_chains ? 'Networks with active monitoring' : 'No chains configured'}
              </Text>
            </Card>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card shadow="sm" padding="lg" radius="md" withBorder>
              <Group justify="space-between" mb="xs">
                <Text fw={500}>Recent Activity</Text>
                <IconActivity size="1.2rem" />
              </Group>
              <Text size="xl" fw={700} c="orange">
                {activityCount}
              </Text>
              <Text size="sm" c="dimmed">
                {activityCount > 0 ? 'Events recorded recently' : 'No recent activity'}
              </Text>
            </Card>
          </Grid.Col>
        </Grid>
      )}

      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Title order={3}>Getting Started</Title>
            <Badge color={isChecklistComplete ? 'green' : 'blue'} variant="light">
              {isChecklistComplete ? 'All set' : 'In progress'}
            </Badge>
          </Group>
          <Text>
            Build your monitoring workspace with a few quick setup steps.
          </Text>
          <Stack gap="xs" ml="md">
            {gettingStartedItems.map((item) => (
              <Group key={item.label} gap="xs">
                <IconCheck size={14} color={item.done ? '#10B981' : '#94A3B8'} />
                <Text size="sm" c={item.done ? 'dark' : 'dimmed'}>
                  {item.label}
                </Text>
              </Group>
            ))}
          </Stack>
        </Stack>
      </Card>
    </Stack>
  )
}
