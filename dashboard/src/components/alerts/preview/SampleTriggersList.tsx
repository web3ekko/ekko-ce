/**
 * Sample Triggers List Component
 *
 * Displays a list of sample events that would have triggered the alert
 */

import { useState } from 'react'
import {
  Stack,
  Card,
  Group,
  Text,
  Badge,
  Collapse,
  Button,
  Code,
  Box,
  ScrollArea,
  Tooltip,
  CopyButton,
  ActionIcon,
} from '@mantine/core'
import {
  IconChevronDown,
  IconChevronUp,
  IconBell,
  IconCopy,
  IconCheck,
  IconClock,
  IconAlertCircle,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import type { SampleTrigger, NearMiss } from '../../../services/alerts-api'

interface SampleTriggersListProps {
  triggers: SampleTrigger[]
  nearMisses?: NearMiss[]
  maxVisible?: number
}

interface TriggerItemProps {
  trigger: SampleTrigger
  index: number
  isNearMiss?: boolean
  thresholdDistance?: number
  explanation?: string
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatValue(value: unknown): string {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1000000) {
      return `${(value / 1000000).toFixed(2)}M`
    }
    if (Math.abs(value) >= 1000) {
      return `${(value / 1000).toFixed(2)}K`
    }
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  if (typeof value === 'string' && value.startsWith('0x')) {
    return `${value.slice(0, 10)}...${value.slice(-8)}`
  }
  return String(value)
}

function TriggerItem({ trigger, index, isNearMiss, thresholdDistance, explanation }: TriggerItemProps) {
  const [expanded, setExpanded] = useState(false)

  const primaryValue = trigger.data?.value_usd ?? trigger.data?.value ?? trigger.data?.amount

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
    >
      <Card
        padding="sm"
        radius="sm"
        withBorder
        style={{
          borderColor: isNearMiss
            ? 'var(--mantine-color-yellow-4)'
            : 'var(--mantine-color-default-border)',
          backgroundColor: isNearMiss
            ? 'var(--mantine-color-yellow-0)'
            : undefined,
        }}
      >
        <Stack gap="xs">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
              {isNearMiss ? (
                <Tooltip label="Near miss - almost triggered">
                  <IconAlertCircle size={16} style={{ color: 'var(--mantine-color-yellow-6)', flexShrink: 0 }} />
                </Tooltip>
              ) : (
                <IconBell size={16} style={{ color: 'var(--mantine-color-green-6)', flexShrink: 0 }} />
              )}

              <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
                <Group gap="xs" wrap="nowrap">
                  <IconClock size={12} style={{ opacity: 0.5, flexShrink: 0 }} />
                  <Text size="xs" c="dimmed">
                    {formatTimestamp(trigger.timestamp)}
                  </Text>
                </Group>

                {primaryValue !== undefined && (
                  <Text size="sm" fw={600} truncate>
                    ${formatValue(primaryValue)}
                  </Text>
                )}
              </Stack>
            </Group>

            <Group gap="xs" wrap="nowrap">
              {isNearMiss && thresholdDistance !== undefined && (
                <Badge size="xs" color="yellow" variant="light">
                  {thresholdDistance.toFixed(1)}% away
                </Badge>
              )}

              {!isNearMiss && (
                <Badge size="xs" color="green" variant="light">
                  Match
                </Badge>
              )}

              <ActionIcon
                variant="subtle"
                size="sm"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </ActionIcon>
            </Group>
          </Group>

          <Collapse in={expanded}>
            <Stack gap="xs" mt="xs">
              {trigger.matched_condition && (
                <Box>
                  <Text size="xs" c="dimmed" mb={4}>
                    {isNearMiss ? 'Condition' : 'Matched Condition'}:
                  </Text>
                  <Code size="xs">{trigger.matched_condition}</Code>
                </Box>
              )}

              {explanation && (
                <Text size="xs" c="dimmed" fs="italic">
                  {explanation}
                </Text>
              )}

              <Box>
                <Group justify="space-between" mb={4}>
                  <Text size="xs" c="dimmed">Event Data:</Text>
                  <CopyButton value={JSON.stringify(trigger.data, null, 2)}>
                    {({ copied, copy }) => (
                      <Tooltip label={copied ? 'Copied!' : 'Copy JSON'}>
                        <ActionIcon variant="subtle" size="xs" onClick={copy}>
                          {copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
                        </ActionIcon>
                      </Tooltip>
                    )}
                  </CopyButton>
                </Group>
                <ScrollArea.Autosize mah={150}>
                  <Code block size="xs">
                    {JSON.stringify(trigger.data, null, 2)}
                  </Code>
                </ScrollArea.Autosize>
              </Box>
            </Stack>
          </Collapse>
        </Stack>
      </Card>
    </motion.div>
  )
}

export function SampleTriggersList({
  triggers,
  nearMisses = [],
  maxVisible = 5,
}: SampleTriggersListProps) {
  const [showAll, setShowAll] = useState(false)

  const visibleTriggers = showAll ? triggers : triggers.slice(0, maxVisible)
  const hasMore = triggers.length > maxVisible

  if (triggers.length === 0 && nearMisses.length === 0) {
    return (
      <Card padding="lg" radius="md" withBorder>
        <Stack align="center" gap="sm">
          <IconBell size={32} style={{ opacity: 0.3 }} />
          <Text c="dimmed" ta="center">
            No events would have triggered this alert
            {nearMisses.length === 0 && ' (and no near misses detected)'}
          </Text>
        </Stack>
      </Card>
    )
  }

  return (
    <Stack gap="sm">
      {triggers.length > 0 && (
        <>
          <Group justify="space-between" align="center">
            <Text size="sm" fw={600}>
              Sample Triggers ({triggers.length})
            </Text>
            {hasMore && (
              <Button
                variant="subtle"
                size="xs"
                rightSection={showAll ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
                onClick={() => setShowAll(!showAll)}
              >
                {showAll ? 'Show Less' : `Show All (${triggers.length})`}
              </Button>
            )}
          </Group>

          <AnimatePresence>
            <Stack gap="xs">
              {visibleTriggers.map((trigger, index) => (
                <TriggerItem
                  key={`trigger-${trigger.timestamp}-${index}`}
                  trigger={trigger}
                  index={index}
                />
              ))}
            </Stack>
          </AnimatePresence>
        </>
      )}

      {nearMisses.length > 0 && (
        <>
          <Group justify="space-between" align="center" mt="md">
            <Group gap="xs">
              <Text size="sm" fw={600}>
                Near Misses ({nearMisses.length})
              </Text>
              <Tooltip label="Events that were close to triggering but didn't meet the threshold">
                <IconAlertCircle size={14} style={{ opacity: 0.5 }} />
              </Tooltip>
            </Group>
          </Group>

          <Stack gap="xs">
            {nearMisses.slice(0, 3).map((miss, index) => (
              <TriggerItem
                key={`miss-${miss.timestamp}-${index}`}
                trigger={{
                  timestamp: miss.timestamp,
                  data: miss.data,
                  matched_condition: '',
                }}
                index={index}
                isNearMiss
                thresholdDistance={miss.threshold_distance}
                explanation={miss.explanation}
              />
            ))}
          </Stack>
        </>
      )}
    </Stack>
  )
}

export default SampleTriggersList
