/**
 * Alert Statistics Grid Component
 * 
 * Displays key alert metrics in a responsive grid layout
 * matching the Wallet page's stats card design
 */

import React from 'react'
import {
  Grid,
  Paper,
  Group,
  Text,
  ThemeIcon,
  Stack,
} from '@mantine/core'
import {
  IconBell,
  IconActivityHeartbeat,
  IconTemplate,
  IconNetwork,
  IconTrendingUp,
  IconTrendingDown,
} from '@tabler/icons-react'

interface AlertStats {
  activeAlerts: number
  triggeredToday: number
  alertTemplates: number
  networksMonitored: number
  change24h?: {
    value: number
    isPositive: boolean
  }
}

interface AlertStatsGridProps {
  stats?: AlertStats
  isLoading?: boolean
}

export function AlertStatsGrid({ stats, isLoading = false }: AlertStatsGridProps) {
  // Default stats if not provided
  const defaultStats: AlertStats = {
    activeAlerts: 0,
    triggeredToday: 0,
    alertTemplates: 0,
    networksMonitored: 0,
  }

  const currentStats = stats || defaultStats

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`
    }
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toString()
  }

  const statCards = [
    {
      title: 'Active Alerts',
      value: currentStats.activeAlerts,
      icon: IconBell,
      color: 'blue',
      description: 'Currently monitoring',
    },
    {
      title: 'Triggered Today',
      value: currentStats.triggeredToday,
      icon: IconActivityHeartbeat,
      color: 'green',
      description: 'Last 24 hours',
      change: currentStats.change24h,
    },
    {
      title: 'Alert Templates',
      value: currentStats.alertTemplates,
      icon: IconTemplate,
      color: 'teal',
      description: 'Available templates',
    },
    {
      title: 'Networks',
      value: currentStats.networksMonitored,
      icon: IconNetwork,
      color: 'orange',
      description: 'Active networks',
    },
  ]

  return (
    <Grid>
      {statCards.map((stat, index) => (
        <Grid.Col key={index} span={{ base: 12, xs: 6, md: 3 }}>
          <Paper p="md" radius="md" withBorder h="100%">
            <Stack gap="xs">
              <Group justify="space-between" align="flex-start">
                <div>
                  <Text size="xs" c="dimmed" fw={500} tt="uppercase">
                    {stat.title}
                  </Text>
                  <Text size="xl" fw={700} mt={4}>
                    {formatNumber(stat.value)}
                  </Text>
                </div>
                <ThemeIcon
                  size="lg"
                  radius="md"
                  variant="light"
                  color={stat.color}
                >
                  <stat.icon size={20} />
                </ThemeIcon>
              </Group>

              <div>
                {stat.change && (
                  <Group gap={4}>
                    {stat.change.isPositive ? (
                      <IconTrendingUp size={14} color="var(--mantine-color-teal-6)" />
                    ) : (
                      <IconTrendingDown size={14} color="var(--mantine-color-red-6)" />
                    )}
                    <Text
                      size="xs"
                      c={stat.change.isPositive ? 'teal' : 'red'}
                      fw={500}
                    >
                      {stat.change.isPositive ? '+' : ''}{stat.change.value}%
                    </Text>
                  </Group>
                )}
                <Text size="xs" c="dimmed">
                  {stat.description}
                </Text>
              </div>
            </Stack>
          </Paper>
        </Grid.Col>
      ))}
    </Grid>
  )
}
