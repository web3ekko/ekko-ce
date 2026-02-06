import { Card, Group, Progress, Stack, Text, ThemeIcon } from '@mantine/core'
import { IconAlertCircle, IconCheck, IconSparkles } from '@tabler/icons-react'
import type { NLPJobStatus } from '../../hooks/useNLPWebSocket'

interface ProgressIndicatorProps {
  status: NLPJobStatus
  message?: string | null
  percent?: number | null
}

export function ProgressIndicator({ status, message, percent }: ProgressIndicatorProps) {
  const isComplete = status === 'completed'
  const isError = status === 'error'

  const icon = isComplete ? <IconCheck size={16} /> : isError ? <IconAlertCircle size={16} /> : <IconSparkles size={16} />
  const color = isComplete ? 'green' : isError ? 'red' : 'blue'
  const progressValue = isComplete ? 100 : isError ? 100 : typeof percent === 'number' && Number.isFinite(percent) ? percent : 65
  const progressLabel =
    typeof percent === 'number' && Number.isFinite(percent) && !isComplete && !isError ? `${Math.round(percent)}%` : null

  return (
    <Card radius="md" withBorder p="md">
      <Stack gap="xs">
        <Group justify="space-between">
          <Group gap="xs">
            <ThemeIcon size="sm" radius="xl" variant="light" color={color}>
              {icon}
            </ThemeIcon>
            <Text size="sm" fw={600}>
              {isComplete ? 'Analysis Complete' : isError ? 'Analysis Failed' : 'Analyzing'}
            </Text>
          </Group>
          <Text size="xs" c="dimmed">
            {progressLabel || status}
          </Text>
        </Group>

        <Text size="xs" c={isError ? 'red' : 'dimmed'}>
          {message || (isComplete ? 'Ready for review.' : 'Working on your alert...')}
        </Text>

        <Progress
          value={progressValue}
          color={color}
          radius="xl"
          size="sm"
          striped={!isComplete && !isError}
          animated={!isComplete && !isError}
        />
      </Stack>
    </Card>
  )
}

export default ProgressIndicator
