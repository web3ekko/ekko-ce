/**
 * Compact Stats Row Component
 *
 * Inline stats display with icons for page headers
 */

import { Card, Group, Text, Badge, type MantineColor } from '@mantine/core'
import type { ReactNode } from 'react'

export interface StatItem {
  icon: ReactNode
  iconColor?: string
  label: string
  value: string | number
  badge?: {
    text: string
    color: MantineColor
    variant?: 'filled' | 'light' | 'dot' | 'outline'
  }
}

interface CompactStatsRowProps {
  stats: StatItem[]
  rightSection?: ReactNode
  background?: string
}

export function CompactStatsRow({
  stats,
  rightSection,
  background = '#F8FAFC',
}: CompactStatsRowProps) {
  return (
    <Card padding="xs" radius="sm" style={{ background, border: '1px solid #E6E9EE' }}>
      <Group justify="space-between" gap="lg">
        <Group gap="lg">
          {stats.map((stat, index) => (
            <Group key={index} gap={6}>
              <span style={{ color: stat.iconColor || '#64748B', display: 'flex' }}>
                {stat.icon}
              </span>
              <Text size="xs" c="#475569">{stat.label}:</Text>
              <Text size="xs" fw={700} c="#0F172A">{stat.value}</Text>
              {stat.badge && (
                <Badge size="xs" color={stat.badge.color} variant={stat.badge.variant || 'light'}>
                  {stat.badge.text}
                </Badge>
              )}
            </Group>
          ))}
        </Group>
        {rightSection}
      </Group>
    </Card>
  )
}
