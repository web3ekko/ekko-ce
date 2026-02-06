/**
 * Preview Summary Card Component
 *
 * Displays key statistics from alert preview/dry-run results
 */

import { Card, Group, Stack, Text, SimpleGrid, ThemeIcon, Tooltip } from '@mantine/core'
import {
  IconChartBar,
  IconBell,
  IconPercentage,
  IconClock,
  IconCalendar,
} from '@tabler/icons-react'
import { motion } from 'framer-motion'
import type { PreviewSummary } from '../../../services/alerts-api'

interface PreviewSummaryCardProps {
  summary: PreviewSummary
  timeRange?: string
}

interface StatItemProps {
  icon: React.ReactNode
  label: string
  value: string | number
  color: string
  tooltip?: string
  delay: number
}

function StatItem({ icon, label, value, color, tooltip, delay }: StatItemProps) {
  const content = (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
    >
      <Group gap="sm" wrap="nowrap">
        <ThemeIcon size="lg" radius="md" color={color} variant="light">
          {icon}
        </ThemeIcon>
        <Stack gap={2}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
            {label}
          </Text>
          <Text size="lg" fw={700}>
            {value}
          </Text>
        </Stack>
      </Group>
    </motion.div>
  )

  if (tooltip) {
    return (
      <Tooltip label={tooltip} position="top" withArrow>
        {content}
      </Tooltip>
    )
  }

  return content
}

export function PreviewSummaryCard({ summary, timeRange }: PreviewSummaryCardProps) {
  const formatNumber = (num: number): string => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toLocaleString()
  }

  const formatPercent = (rate: number): string => {
    return `${(rate * 100).toFixed(2)}%`
  }

  const formatTime = (ms: number): string => {
    if (ms < 1000) {
      return `${ms.toFixed(0)}ms`
    }
    return `${(ms / 1000).toFixed(2)}s`
  }

  const getTriggerRateColor = (rate: number): string => {
    if (rate === 0) return 'gray'
    if (rate < 0.01) return 'green' // Low trigger rate is usually good
    if (rate < 0.05) return 'yellow'
    return 'orange' // High trigger rate might indicate noise
  }

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Text size="sm" fw={600} c="dimmed">
            Preview Results
          </Text>
          {timeRange && (
            <Group gap="xs">
              <IconCalendar size={14} style={{ opacity: 0.5 }} />
              <Text size="xs" c="dimmed">
                {timeRange} historical data
              </Text>
            </Group>
          )}
        </Group>

        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
          <StatItem
            icon={<IconChartBar size={18} />}
            label="Events Evaluated"
            value={formatNumber(summary.total_events_evaluated)}
            color="blue"
            tooltip={`${summary.total_events_evaluated.toLocaleString()} total events analyzed`}
            delay={0}
          />

          <StatItem
            icon={<IconBell size={18} />}
            label="Would Trigger"
            value={formatNumber(summary.would_have_triggered)}
            color={summary.would_have_triggered > 0 ? 'green' : 'gray'}
            tooltip={`${summary.would_have_triggered.toLocaleString()} events would have triggered this alert`}
            delay={0.1}
          />

          <StatItem
            icon={<IconPercentage size={18} />}
            label="Trigger Rate"
            value={formatPercent(summary.trigger_rate)}
            color={getTriggerRateColor(summary.trigger_rate)}
            tooltip="Percentage of events that would trigger this alert"
            delay={0.2}
          />

          <StatItem
            icon={<IconClock size={18} />}
            label="Est. Daily"
            value={summary.estimated_daily_triggers.toFixed(1)}
            color="teal"
            tooltip="Estimated number of alerts per day based on historical data"
            delay={0.3}
          />
        </SimpleGrid>

        {summary.evaluation_time_ms > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <Text size="xs" c="dimmed" ta="right">
              Evaluated in {formatTime(summary.evaluation_time_ms)}
            </Text>
          </motion.div>
        )}
      </Stack>
    </Card>
  )
}

export default PreviewSummaryCard
