/**
 * Quick Template Bar Component
 *
 * Horizontal scrollable template selection with collapse support
 */

import { useState, type ReactNode } from 'react'
import {
  Card,
  Group,
  Text,
  Badge,
  ActionIcon,
  Paper,
  Stack,
  ThemeIcon,
  ScrollArea,
  Collapse,
} from '@mantine/core'
import {
  IconTemplate,
  IconChevronDown,
  IconChevronUp,
  IconPlus,
} from '@tabler/icons-react'

export interface Template {
  id: string
  name: string
  description: string
  icon: React.ComponentType<{ size: number }>
  color: string
  category?: string
  usage?: number
}

interface QuickTemplateBarProps {
  templates: Template[]
  onSelectTemplate: (templateId: string) => void
  onCreateCustom?: () => void
  title?: string
  collapsible?: boolean
  defaultCollapsed?: boolean
}

export function QuickTemplateBar({
  templates,
  onSelectTemplate,
  onCreateCustom,
  title = 'Quick Templates',
  collapsible = true,
  defaultCollapsed = false,
}: QuickTemplateBarProps) {
  const [isExpanded, setIsExpanded] = useState(!defaultCollapsed)

  return (
    <Card padding="sm" radius="sm" withBorder style={{ background: '#FAFBFC' }}>
      <Group justify="space-between" align="center" mb={isExpanded ? 'sm' : 0}>
        <Group gap="xs">
          <IconTemplate size={16} color="#64748B" />
          <Text size="sm" fw={600} c="#0F172A">{title}</Text>
          <Badge size="xs" variant="light" color="gray">{templates.length}</Badge>
        </Group>
        {collapsible && (
          <ActionIcon variant="subtle" size="xs" onClick={() => setIsExpanded(!isExpanded)}>
            {isExpanded ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          </ActionIcon>
        )}
      </Group>

      <Collapse in={isExpanded}>
        <ScrollArea scrollbarSize={4}>
          <Group gap="xs" wrap="nowrap" pb={4}>
            {templates.map((template) => {
              const Icon = template.icon
              return (
                <Paper
                  key={template.id}
                  p="xs"
                  radius="sm"
                  withBorder
                  style={{
                    minWidth: 140,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    border: '1px solid #E6E9EE',
                  }}
                  onClick={() => onSelectTemplate(template.id)}
                >
                  <Group gap={6} wrap="nowrap">
                    <ThemeIcon size="sm" variant="light" color={template.color} radius="sm">
                      <Icon size={12} />
                    </ThemeIcon>
                    <div style={{ minWidth: 0 }}>
                      <Text size="xs" fw={600} c="#0F172A" lineClamp={1}>
                        {template.name}
                      </Text>
                      <Text size="xs" c="#64748B" lineClamp={1}>
                        {template.description}
                      </Text>
                    </div>
                  </Group>
                </Paper>
              )
            })}
            {onCreateCustom && (
              <Paper
                p="xs"
                radius="sm"
                style={{
                  minWidth: 100,
                  cursor: 'pointer',
                  border: '1px dashed #CBD5E1',
                  background: '#F8FAFC',
                }}
                onClick={onCreateCustom}
              >
                <Stack align="center" gap={4}>
                  <IconPlus size={14} color="#64748B" />
                  <Text size="xs" c="#64748B">Custom</Text>
                </Stack>
              </Paper>
            )}
          </Group>
        </ScrollArea>
      </Collapse>
    </Card>
  )
}
