/**
 * Executive Dashboard Home Page Component
 * 
 * Enhanced dashboard with executive-focused features:
 * - Critical Alert Banner
 * - Executive Portfolio Cards
 * - Chain-Specific Monitoring Widgets
 * - Activity Timeline
 * - Natural Language Alert Input
 */

import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Title, Text, Stack, Grid, Card, SimpleGrid, Button, Badge, Group, Modal } from '@mantine/core'
import { IconSparkles, IconWallet, IconBell, IconUserPlus, IconPlugConnected, IconAlertTriangle, IconCheck, IconX, IconBook, IconFileText } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useDisclosure } from '@mantine/hooks'
import { motion } from 'framer-motion'
import { useAuthStore } from '../../store/auth'
import { useWalletStore } from '../../store/wallets'
import { useWebSocketStore } from '../../store/websocket'
import { useDashboardStats } from '../../hooks/useDashboardStats'
import { notificationsApiService } from '../../services/notifications-api'

// Import our new executive dashboard components
import { ExecutivePortfolioCards } from '../../components/dashboard/ExecutivePortfolioCards'
import { ChainMonitoringWidgets } from '../../components/dashboard/ChainMonitoringWidgets'
import { TransactionNewsfeed } from '../../components/dashboard/TransactionNewsfeed'
import { NaturalLanguageAlertInput } from '../../components/dashboard/NaturalLanguageAlertInput'
import { CriticalAlertBanner } from '../../components/dashboard/CriticalAlertBanner'
import { CreateAlertOptimized } from '../../components/alerts/CreateAlertOptimized'
import { AddWalletModal } from '../../components/wallets/AddWalletModal'
import { InviteMemberModal } from '../../components/team/InviteMemberModal'
import { ConfigureWebhookModal } from '../../components/notifications/ConfigureWebhookModal'
import { AlertGroupsWidget } from '../../components/dashboard/AlertGroupsWidget'
import { WalletGroupsWidget } from '../../components/dashboard/WalletGroupsWidget'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05  // Faster stagger for denser feel
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 8 },  // Subtler entrance
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.2 }  // Snappier
  }
}

export function DashboardHomeExecutive() {
  const { user } = useAuthStore()
  const { accounts } = useWalletStore()
  const { activeAlerts, isConnected, systemStatus } = useWebSocketStore()
  const navigate = useNavigate()
  const [createModalOpened, { open: openCreateModal, close: closeCreateModal }] = useDisclosure(false)
  const [addWalletModalOpened, { open: openAddWalletModal, close: closeAddWalletModal }] = useDisclosure(false)
  const [inviteModalOpened, { open: openInviteModal, close: closeInviteModal }] = useDisclosure(false)
  const [webhookModalOpened, { open: openWebhookModal, close: closeWebhookModal }] = useDisclosure(false)
  const [notificationTotals, setNotificationTotals] = useState({ delivered: 0, failed: 0, channels: 0 })
  const [isNotificationStatsLoading, setIsNotificationStatsLoading] = useState(true)
  const { stats: dashboardStats, isLoading: isStatsLoading } = useDashboardStats()

  const handleAlertCreated = () => {
    console.log('Alert created, closing modal')
    closeCreateModal()
  }

  const handleOpenCreateModal = () => {
    console.log('Opening create modal')
    openCreateModal()
  }

  useEffect(() => {
    let isActive = true

    const loadNotificationStats = async () => {
      setIsNotificationStatsLoading(true)
      try {
        const response = await notificationsApiService.getChannels({ page_size: 200 })
        const channels = response.results || []
        const stats = await Promise.all(
          channels.map((channel) =>
            notificationsApiService.getChannelStats(channel.id).catch(() => null)
          )
        )

        const totals = stats.reduce(
          (acc, stat) => {
            if (!stat) return acc
            acc.delivered += stat.success_count
            acc.failed += stat.failure_count
            return acc
          },
          { delivered: 0, failed: 0 }
        )

        if (isActive) {
          setNotificationTotals({
            delivered: totals.delivered,
            failed: totals.failed,
            channels: channels.length,
          })
        }
      } catch (error) {
        console.error('Failed to load notification stats:', error)
      } finally {
        if (isActive) {
          setIsNotificationStatsLoading(false)
        }
      }
    }

    loadNotificationStats()

    return () => {
      isActive = false
    }
  }, [])

  const quickActions = useMemo(() => {
    const hasWallets = (dashboardStats?.wallets.total ?? accounts.length) > 0

    if (!hasWallets) {
      return [
        {
          title: 'Connect Wallet',
          description: 'Start monitoring your assets',
          icon: IconWallet,
          color: '#2563EB',
          action: openAddWalletModal
        },
        {
          title: 'Create alert',
          description: 'Start with natural language',
          icon: IconBell,
          color: '#14B8A6',
          action: handleOpenCreateModal
        },
        {
          title: 'Marketplace',
          description: 'Browse alert templates',
          icon: IconSparkles,
          color: '#FB923C',
          action: () => navigate('/dashboard/marketplace')
        },
        {
          title: 'Documentation',
          description: 'Learn about features',
          icon: IconBook,
          color: '#64748B',
          action: () => window.open('https://docs.ekko.local', '_blank')
        }
      ]
    }

    return [
      {
        title: 'Add wallet',
        description: 'Track a new address',
        icon: IconWallet,
        color: '#2563EB',
        action: openAddWalletModal
      },
      {
        title: 'Create alert',
        description: 'Natural language monitoring',
        icon: IconBell,
        color: '#14B8A6',
        action: handleOpenCreateModal
      },
      {
        title: 'Invite team',
        description: 'Share access & permissions',
        icon: IconUserPlus,
        color: '#FB923C',
        action: openInviteModal
      },
      {
        title: 'Configure webhook',
        description: 'Pipe alerts into your stack',
        icon: IconPlugConnected,
        color: '#EF4444',
        action: openWebhookModal
      },
    ]
  }, [accounts.length, dashboardStats?.wallets.total, navigate])

  const healthStats = useMemo(() => [
    {
      label: 'Notifications delivered',
      value: isNotificationStatsLoading ? 'Loading' : notificationTotals.delivered,
      variant: notificationTotals.failed > 0 ? 'warning' : 'success',
    },
    {
      label: 'Failed deliveries',
      value: isNotificationStatsLoading ? 'Loading' : notificationTotals.failed,
      variant: notificationTotals.failed > 0 ? 'warning' : 'success',
    },
    {
      label: 'Active alerts',
      value: isStatsLoading ? 'Loading' : (dashboardStats?.alerts.active ?? activeAlerts),
      variant: 'info',
    },
    {
      label: 'System Status',
      value: isConnected ? 'Online' : 'Offline',
      variant: isConnected && systemStatus.status === 'operational' ? 'success' : 'warning',
    },
  ], [
    activeAlerts,
    dashboardStats?.alerts.active,
    isConnected,
    isNotificationStatsLoading,
    isStatsLoading,
    notificationTotals.delivered,
    notificationTotals.failed,
    systemStatus.status,
  ])

  const checklist = useMemo(() => {
    const walletCount = dashboardStats?.wallets.total ?? accounts.length
    const alertsCount = dashboardStats?.alerts.total ?? 0
    const hasChannels = notificationTotals.channels > 0

    return [
      { label: 'Add at least one wallet', done: walletCount > 0, action: 'Add wallet' },
      { label: 'Create your first alert', done: alertsCount > 0, action: 'Create alert' },
      { label: 'Set a notification channel', done: hasChannels, action: 'Edit channels' },
    ]
  }, [accounts.length, dashboardStats?.alerts.total, dashboardStats?.wallets.total, notificationTotals.channels])

  // Show welcome message for new users
  useEffect(() => {
    const showWelcome = localStorage.getItem('showWelcomeMessage')
    if (showWelcome === 'true') {
      notifications.show({
        title: 'Welcome to Ekko Executive Dashboard! 🎉',
        message: 'Your enhanced monitoring dashboard is now active. All critical alerts and portfolio updates will appear here.',
        color: 'teal',
        icon: <IconSparkles size={20} />,
        autoClose: 8000,
      })
      localStorage.removeItem('showWelcomeMessage')
    }
  }, [])

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      <Stack gap="md">
        {/* Critical Alert Banner - Always at top when active */}
        <CriticalAlertBanner />

        {/* Welcome Header - Compact */}
        <motion.div variants={itemVariants}>
          <Group justify="space-between" align="center">
            <div>
              <Title order={2} mb={4}>
                Welcome back, {user?.email}!
              </Title>
              <Text c="dimmed" size="sm">
                Portfolio overview and monitoring alerts
              </Text>
            </div>
            <Group gap="xs">
              <Button size="xs" variant="light" color="teal" leftSection={<IconFileText size={14} />} onClick={() => notifications.show({ title: 'Report Generated', message: 'Executive summary sent to email', color: 'teal' })}>Generate Report</Button>
              <Button size="xs" color="blue" leftSection={<IconWallet size={14} />} onClick={openAddWalletModal}>Add wallet</Button>
              <Button size="xs" variant="outline" color="blue" leftSection={<IconBell size={14} />} onClick={handleOpenCreateModal}>Create alert</Button>
            </Group>
          </Group>
        </motion.div>

        {/* Quick Actions - Compact inline */}
        <motion.div variants={itemVariants}>
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="xs">
            {quickActions.map((action) => (
              <Card
                key={action.title}
                withBorder
                radius="md"
                shadow="sm"
                padding="xs"
                style={{
                  borderLeft: `3px solid ${action.color}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  backgroundColor: '#FFFFFF',
                }}
                onClick={() => {
                  if (action.action) {
                    action.action()
                  }
                }}
                styles={{
                  root: {
                    '&:hover': {
                      transform: 'translateY(-2px)',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                    }
                  }
                }}
              >
                <Group gap={6} wrap="nowrap">
                  <action.icon size={16} color={action.color} />
                  <Text fw={600} size="xs" c="#0F172A" lineClamp={1}>{action.title}</Text>
                </Group>
              </Card>
            ))}
          </SimpleGrid>
        </motion.div>

        {/* Health Stats - Compact inline row */}
        <motion.div variants={itemVariants}>
          <Card withBorder radius="sm" padding="xs" style={{ background: '#F8FAFC' }}>
            <Group justify="space-between" align="center" gap="xs">
              <Group gap="lg">
                {healthStats.map((stat) => (
                  <Group key={stat.label} gap={6} align="center">
                    {stat.variant === 'warning' && <IconAlertTriangle size={14} color="#FB923C" />}
                    {stat.variant === 'success' && <IconCheck size={14} color="#10B981" />}
                    <Text size="xs" c="#475569">{stat.label}:</Text>
                    <Text size="xs" fw={700} c="#0F172A">
                      {stat.value}
                    </Text>
                  </Group>
                ))}
              </Group>
              <Badge size="xs" color="green" variant="dot">Live</Badge>
            </Group>
          </Card>
        </motion.div>

        {/* Natural Language Alert Input - Persistent and prominent */}
        <motion.div variants={itemVariants}>
          <NaturalLanguageAlertInput onInputClick={handleOpenCreateModal} />
        </motion.div>

        {/* Portfolio + Networks - Combined Grid */}
        <motion.div variants={itemVariants}>
          <Grid gutter="sm">
            <Grid.Col span={{ base: 12, lg: 7 }}>
              <Stack gap="md">
                <Stack gap={6}>
                  <Text fw={600} size="sm" c="#0F172A">Portfolio</Text>
                  <ExecutivePortfolioCards />
                </Stack>

                {/* Groups Section */}
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
                  <WalletGroupsWidget />
                  <AlertGroupsWidget />
                </SimpleGrid>
              </Stack>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 5 }}>
              <Stack gap={6}>
                <Text fw={600} size="sm" c="#0F172A">Networks</Text>
                <ChainMonitoringWidgets />
              </Stack>
            </Grid.Col>
          </Grid>
        </motion.div>

        {/* Transactions + Sidebar - Two column bottom */}
        <motion.div variants={itemVariants}>
          <Grid gutter="sm">
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <TransactionNewsfeed />
            </Grid.Col>

            {/* Compact sidebar */}
            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Stack gap="xs">
                {/* Setup checklist - compact */}
                <Card withBorder radius="sm" padding="xs" style={{ borderLeft: '3px solid #2563EB' }}>
                  <Stack gap={6}>
                    <Text fw={600} size="xs" c="#0F172A">Setup</Text>
                    {checklist.map((item) => (
                      <Group key={item.label} justify="space-between" gap={4}>
                        <Group gap={4}>
                          {item.done ? <IconCheck size={12} color="#10B981" /> : <IconX size={12} color="#FB923C" />}
                          <Text size="xs" c="#475569">{item.label}</Text>
                        </Group>
                        <Button
                          size="compact-xs"
                          variant="subtle"
                          color="blue"
                          style={{ padding: '2px 6px', fontSize: 10 }}
                          onClick={() => {
                            if (item.action === 'Create alert') {
                              handleOpenCreateModal()
                            } else if (item.action === 'Add wallet') {
                              openAddWalletModal()
                            } else if (item.action === 'Edit channels') {
                              navigate('/dashboard/settings/notifications')
                            }
                          }}
                        >
                          {item.action}
                        </Button>
                      </Group>
                    ))}
                  </Stack>
                </Card>

                {/* Metrics - compact inline */}
                <Card withBorder radius="sm" padding="xs" style={{ borderLeft: '3px solid #14B8A6' }}>
                  <Group justify="space-between" align="center">
                    <Text fw={600} size="xs" c="#0F172A">Today</Text>
                    <Group gap="md">
                      <div>
                        <Text size="xs" c="dimmed">Executions</Text>
                        <Text fw={700} size="sm" c="#0F172A">
                          {isStatsLoading ? '—' : dashboardStats?.activity.executions_24h ?? 0}
                        </Text>
                      </div>
                      <div>
                        <Text size="xs" c="dimmed">Triggered</Text>
                        <Text fw={700} size="sm" c="#0F172A">
                          {isStatsLoading ? '—' : dashboardStats?.activity.triggered_24h ?? 0}
                        </Text>
                      </div>
                    </Group>
                  </Group>
                </Card>
              </Stack>
            </Grid.Col>
          </Grid>
        </motion.div>
      </Stack>

      <Modal
        opened={createModalOpened}
        onClose={closeCreateModal}
        title={<Text fw={600} size="sm">Create New Alert</Text>}
        size="lg"
      >
        <CreateAlertOptimized onCancel={closeCreateModal} onAlertCreated={handleAlertCreated} />
      </Modal>

      <AddWalletModal
        opened={addWalletModalOpened}
        onClose={closeAddWalletModal}
        onWalletAdded={() => {}}
      />

      <InviteMemberModal
        opened={inviteModalOpened}
        onClose={closeInviteModal}
        onSubmit={() => {
          notifications.show({ title: 'Invite Sent', message: 'Team member invited', color: 'green' })
          closeInviteModal()
        }}
      />

      <ConfigureWebhookModal
        opened={webhookModalOpened}
        onClose={closeWebhookModal}
      />
    </motion.div>
  )
}
