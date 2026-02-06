import { Badge, Card, Group, Paper, SimpleGrid, Stack, Switch, Text } from '@mantine/core'

type SummaryItem = {
  label: string
  value: string
  badgeColor?: string
}

interface AlertDetailSummaryCardProps {
  eventType: string
  subEvent: string
  alertType: string
  targetSummary: string
  processingStatus: string
  enabled: boolean
  isSaving: boolean
  createdAt?: string
  updatedAt?: string
  onToggle: (nextEnabled: boolean) => void
}

const formatDateTime = (value?: string): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

const getProcessingColor = (status: string) => {
  if (status === 'failed') return 'red'
  if (status === 'completed') return 'green'
  return 'gray'
}

export function AlertDetailSummaryCard({
  eventType,
  subEvent,
  alertType,
  targetSummary,
  processingStatus,
  enabled,
  isSaving,
  createdAt,
  updatedAt,
  onToggle,
}: AlertDetailSummaryCardProps) {
  const items: SummaryItem[] = [
    { label: 'Event', value: eventType || '—', badgeColor: 'blue' },
    { label: 'Sub-event', value: subEvent || '—', badgeColor: 'gray' },
    { label: 'Alert Type', value: alertType || '—', badgeColor: 'gray' },
    { label: 'Target', value: targetSummary || '—' },
    { label: 'Processing', value: processingStatus || '—', badgeColor: getProcessingColor(processingStatus) },
  ]

  if (createdAt) {
    items.push({ label: 'Created', value: formatDateTime(createdAt) })
  }

  if (updatedAt) {
    items.push({ label: 'Updated', value: formatDateTime(updatedAt) })
  }

  return (
    <Card withBorder radius="md" p="md">
      <Group justify="space-between" align="center" mb="md" wrap="wrap">
        <Group gap="xs">
          <Text fw={700} c="#0F172A">
            Summary
          </Text>
          <Badge color={enabled ? 'green' : 'gray'} variant="light">
            {enabled ? 'Enabled' : 'Disabled'}
          </Badge>
        </Group>
        <Group gap="xs" wrap="wrap">
          <Text size="xs" c="dimmed">
            Enabled
          </Text>
          <Switch
            checked={enabled}
            onChange={(e) => onToggle(e.currentTarget.checked)}
            disabled={isSaving}
            aria-label="Toggle alert enabled"
          />
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
        {items.map((item) => (
          <Paper
            key={item.label}
            withBorder
            radius="md"
            p="sm"
            style={{ backgroundColor: 'var(--surface-subtle)' }}
          >
            <Stack gap={6}>
              <Text size="xs" c="dimmed">
                {item.label}
              </Text>
              {item.badgeColor ? (
                <Badge size="sm" variant="light" color={item.badgeColor}>
                  {item.value}
                </Badge>
              ) : (
                <Text size="sm" fw={600} c="#0F172A">
                  {item.value}
                </Text>
              )}
            </Stack>
          </Paper>
        ))}
      </SimpleGrid>
    </Card>
  )
}

export default AlertDetailSummaryCard
