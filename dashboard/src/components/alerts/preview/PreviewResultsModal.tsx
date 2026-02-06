/**
 * Preview Results Modal Component
 *
 * Main modal displaying alert dry-run/preview results including
 * summary statistics and sample trigger events
 */

import {
  Modal,
  Stack,
  Group,
  Button,
  Text,
  Alert,
  Tabs,
  Badge,
  Loader,
  Center,
  Box,
} from '@mantine/core'
import {
  IconChartBar,
  IconBell,
  IconAlertCircle,
  IconAdjustments,
  IconCheck,
  IconX,
  IconInfoCircle,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { PreviewSummaryCard } from './PreviewSummaryCard'
import { SampleTriggersList } from './SampleTriggersList'
import type { PreviewResult } from '../../../services/alerts-api'

interface PreviewResultsModalProps {
  opened: boolean
  onClose: () => void
  result: PreviewResult | null
  isLoading?: boolean
  onAdjustThreshold?: () => void
  onCreate?: () => void
  timeRange?: string
}

export function PreviewResultsModal({
  opened,
  onClose,
  result,
  isLoading = false,
  onAdjustThreshold,
  onCreate,
  timeRange,
}: PreviewResultsModalProps) {
  const hasNearMisses = result?.near_misses && result.near_misses.length > 0
  const hasTriggers = result?.sample_triggers && result.sample_triggers.length > 0

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <IconChartBar size={20} />
          <Text fw={600}>Alert Preview Results</Text>
          {result?.success && (
            <Badge size="sm" color="green" variant="light">
              Completed
            </Badge>
          )}
        </Group>
      }
      size="lg"
      padding="lg"
    >
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Center py="xl">
              <Stack align="center" gap="md">
                <Loader size="lg" />
                <Text c="dimmed">Evaluating alert against historical data...</Text>
              </Stack>
            </Center>
          </motion.div>
        ) : result ? (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
          >
            <Stack gap="lg">
              {/* Error State */}
              {!result.success && result.error && (
                <Alert
                  icon={<IconX size={16} />}
                  title="Preview Failed"
                  color="red"
                  variant="light"
                >
                  {result.error}
                </Alert>
              )}

              {/* wasmCloud Required Warning */}
              {result.requires_wasmcloud && (
                <Alert
                  icon={<IconInfoCircle size={16} />}
                  title="Advanced Evaluation Required"
                  color="blue"
                  variant="light"
                >
                  <Text size="sm">
                    This alert uses advanced expressions that require wasmCloud evaluation.
                  </Text>
                  {result.wasmcloud_reason && (
                    <Text size="xs" c="dimmed" mt="xs">
                      Reason: {result.wasmcloud_reason}
                    </Text>
                  )}
                </Alert>
              )}

              {/* Summary Statistics */}
              {result.success && (
                <PreviewSummaryCard
                  summary={result.summary}
                  timeRange={timeRange || result.time_range}
                />
              )}

              {/* Evaluation Info */}
              {result.success && (result.expression || result.data_source) && (
                <Box>
                  <Group gap="xs" mb="xs">
                    <Text size="xs" c="dimmed">
                      Evaluation Mode:
                    </Text>
                    <Badge size="xs" variant="light" color="gray">
                      {result.evaluation_mode}
                    </Badge>
                  </Group>
                  {result.expression && (
                    <Text size="xs" c="dimmed" style={{ fontFamily: 'monospace' }}>
                      Expression: {result.expression}
                    </Text>
                  )}
                  {result.data_source && (
                    <Text size="xs" c="dimmed">
                      Data Source: {result.data_source}
                    </Text>
                  )}
                </Box>
              )}

              {/* Triggers and Near Misses Tabs */}
              {result.success && (hasTriggers || hasNearMisses) && (
                <Tabs defaultValue="triggers" variant="outline">
                  <Tabs.List>
                    <Tabs.Tab
                      value="triggers"
                      leftSection={<IconBell size={14} />}
                      rightSection={
                        hasTriggers && (
                          <Badge size="xs" variant="filled" color="green">
                            {result.sample_triggers!.length}
                          </Badge>
                        )
                      }
                    >
                      Sample Triggers
                    </Tabs.Tab>
                    {hasNearMisses && (
                      <Tabs.Tab
                        value="near-misses"
                        leftSection={<IconAlertCircle size={14} />}
                        rightSection={
                          <Badge size="xs" variant="filled" color="yellow">
                            {result.near_misses!.length}
                          </Badge>
                        }
                      >
                        Near Misses
                      </Tabs.Tab>
                    )}
                  </Tabs.List>

                  <Tabs.Panel value="triggers" pt="md">
                    <SampleTriggersList
                      triggers={result.sample_triggers || []}
                      maxVisible={5}
                    />
                  </Tabs.Panel>

                  {hasNearMisses && (
                    <Tabs.Panel value="near-misses" pt="md">
                      <SampleTriggersList
                        triggers={[]}
                        nearMisses={result.near_misses}
                        maxVisible={5}
                      />
                    </Tabs.Panel>
                  )}
                </Tabs>
              )}

              {/* No Results State */}
              {result.success &&
                !hasTriggers &&
                !hasNearMisses &&
                result.summary.total_events_evaluated > 0 && (
                  <Alert
                    icon={<IconInfoCircle size={16} />}
                    title="No Matches Found"
                    color="gray"
                    variant="light"
                  >
                    <Text size="sm">
                      No events in the{' '}
                      {timeRange || result.time_range || 'selected time range'} would have
                      triggered this alert. Consider adjusting your threshold or conditions.
                    </Text>
                  </Alert>
                )}

              {/* Action Buttons */}
              <Group justify="flex-end" mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
                <Button variant="subtle" onClick={onClose}>
                  Close
                </Button>
                {onAdjustThreshold && result.success && (
                  <Button
                    variant="light"
                    leftSection={<IconAdjustments size={16} />}
                    onClick={onAdjustThreshold}
                  >
                    Adjust Threshold
                  </Button>
                )}
                {onCreate && result.success && (
                  <Button
                    leftSection={<IconCheck size={16} />}
                    onClick={onCreate}
                  >
                    Create Alert
                  </Button>
                )}
              </Group>
            </Stack>
          </motion.div>
        ) : (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Center py="xl">
              <Text c="dimmed">No preview results available</Text>
            </Center>
          </motion.div>
        )}
      </AnimatePresence>
    </Modal>
  )
}

export default PreviewResultsModal
