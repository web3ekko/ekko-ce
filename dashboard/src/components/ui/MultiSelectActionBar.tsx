/**
 * Multi-Select Action Bar Component
 *
 * Reusable bulk action bar for list/grid pages with selection support
 */

import { Paper, Group, Checkbox, Text, ActionIcon, Tooltip, Transition } from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import type { ReactNode } from 'react'

export interface BulkAction {
  icon: ReactNode
  label: string
  color: string
  onClick: () => void
}

interface MultiSelectActionBarProps {
  selectedCount: number
  totalCount: number
  onSelectAll: () => void
  onClearSelection: () => void
  actions: BulkAction[]
  mounted?: boolean
}

export function MultiSelectActionBar({
  selectedCount,
  totalCount,
  onSelectAll,
  onClearSelection,
  actions,
  mounted = true,
}: MultiSelectActionBarProps) {
  const isAllSelected = selectedCount === totalCount && totalCount > 0
  const isIndeterminate = selectedCount > 0 && selectedCount < totalCount

  return (
    <Transition mounted={mounted && selectedCount > 0} transition="slide-down" duration={200}>
      {(styles) => (
        <Paper style={styles} p="xs" radius="sm" withBorder bg="#EFF6FF">
          <Group justify="space-between" align="center">
            <Group gap="xs">
              <Checkbox
                checked={isAllSelected}
                indeterminate={isIndeterminate}
                onChange={onSelectAll}
                size="xs"
              />
              <Text size="xs" fw={500} c="#2563EB">
                {selectedCount} selected
              </Text>
            </Group>
            <Group gap="xs">
              {actions.map((action, index) => (
                <Tooltip key={index} label={action.label}>
                  <ActionIcon
                    size="sm"
                    variant="light"
                    color={action.color}
                    onClick={action.onClick}
                  >
                    {action.icon}
                  </ActionIcon>
                </Tooltip>
              ))}
              <ActionIcon size="sm" variant="subtle" onClick={onClearSelection}>
                <IconX size={14} />
              </ActionIcon>
            </Group>
          </Group>
        </Paper>
      )}
    </Transition>
  )
}
