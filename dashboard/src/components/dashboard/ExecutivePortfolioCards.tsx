/**
 * Executive Portfolio Cards Component
 *
 * Executive-level stats driven by live dashboard APIs.
 */

import { useMemo } from 'react'
import { Grid, Group, Text, Badge, ThemeIcon, Center, Loader } from '@mantine/core'
import { IconBell, IconWallet, IconFolder, IconActivity } from '@tabler/icons-react'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { useDashboardStats } from '../../hooks/useDashboardStats'

interface MetricCard {
  id: string
  title: string
  value: number
  subtitle: string
  icon: typeof IconBell
  color: string
}

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)

export function ExecutivePortfolioCards() {
  const { stats, isLoading, error } = useDashboardStats()

  const metrics = useMemo<MetricCard[]>(() => {
    if (!stats) return []

    return [
      {
        id: 'alerts-active',
        title: 'Active Alerts',
        value: stats.alerts.active,
        subtitle: `${formatNumber(stats.alerts.total)} total alerts`,
        icon: IconBell,
        color: 'blue',
      },
      {
        id: 'wallets-watched',
        title: 'Watched Wallets',
        value: stats.wallets.watched,
        subtitle: `${formatNumber(stats.wallets.total)} total wallets`,
        icon: IconWallet,
        color: 'teal',
      },
      {
        id: 'alert-groups',
        title: 'Alert Groups',
        value: stats.groups.total,
        subtitle: `${formatNumber(stats.groups.subscribed)} subscribed`,
        icon: IconFolder,
        color: 'grape',
      },
      {
        id: 'executions',
        title: 'Executions (24h)',
        value: stats.activity.executions_24h,
        subtitle: `${formatNumber(stats.activity.triggered_24h)} triggered`,
        icon: IconActivity,
        color: 'orange',
      },
    ]
  }, [stats])

  if (isLoading) {
    return (
      <Grid gutter="xs">
        <Grid.Col span={{ base: 12 }}>
          <ExecutiveCard variant="elevated" size="default">
            <Center h={140}>
              <Loader size="sm" />
            </Center>
          </ExecutiveCard>
        </Grid.Col>
      </Grid>
    )
  }

  if (error) {
    return (
      <Grid gutter="xs">
        <Grid.Col span={{ base: 12 }}>
          <ExecutiveCard variant="elevated" size="default">
            <Group justify="space-between" align="center">
              <Text fw={600} c="#0F172A">
                Portfolio Summary
              </Text>
              <Badge color="red" variant="light">
                Unavailable
              </Badge>
            </Group>
            <Text size="sm" c="dimmed" mt="sm">
              {error}
            </Text>
          </ExecutiveCard>
        </Grid.Col>
      </Grid>
    )
  }

  return (
    <Grid gutter="xs">
      {metrics.map((metric) => {
        const MetricIcon = metric.icon
        return (
          <Grid.Col key={metric.id} span={{ base: 12, sm: 6, lg: 3 }}>
            <ExecutiveCard variant="elevated" size="default" glowOnHover>
              <Group justify="space-between" align="center" mb="xs">
                <Group gap={8} align="center">
                  <ThemeIcon variant="light" color={metric.color} radius="md" size="md">
                    <MetricIcon size={16} />
                  </ThemeIcon>
                  <Text size="sm" fw={600} c="#0F172A">
                    {metric.title}
                  </Text>
                </Group>
                <Badge size="xs" variant="light" color={metric.color}>
                  Live
                </Badge>
              </Group>

              <Text fz={28} fw={700} lh={1.1} mb={6}>
                {formatNumber(metric.value)}
              </Text>
              <Text size="xs" c="dimmed">
                {metric.subtitle}
              </Text>
            </ExecutiveCard>
          </Grid.Col>
        )
      })}
    </Grid>
  )
}
