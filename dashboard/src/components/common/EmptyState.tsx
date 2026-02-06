/**
 * Empty State Component
 * 
 * Reusable empty state component for when there's no data to display
 */

import { Stack, Title, Text, ThemeIcon } from '@mantine/core'
import { IconInbox } from '@tabler/icons-react'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
}

export function EmptyState({ 
  title, 
  description, 
  icon = <IconInbox size="2rem" />,
  action 
}: EmptyStateProps) {
  return (
    <Stack align="center" gap="md" py="xl">
      <ThemeIcon size="xl" radius="xl" variant="light" color="gray">
        {icon}
      </ThemeIcon>
      
      <Stack align="center" gap="xs">
        <Title order={3} ta="center" c="dimmed">
          {title}
        </Title>
        
        {description && (
          <Text ta="center" c="dimmed" size="sm" maw={400}>
            {description}
          </Text>
        )}
      </Stack>
      
      {action && action}
    </Stack>
  )
}

export default EmptyState
