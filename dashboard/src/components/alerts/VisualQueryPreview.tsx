/**
 * Visual Query Preview Component
 * 
 * Executive-friendly visual representation of the alert query
 */

import { Card, Stack, Group, Text, Box, Badge, ThemeIcon, Divider } from '@mantine/core'
import { 
  IconEye, 
  IconClock, 
  IconMapPin, 
  IconFilter, 
  IconBell,
  IconCheck,
} from '@tabler/icons-react'
import { motion } from 'framer-motion'
import type { VisualQuery } from './CreateAlertOptimized'

interface VisualQueryPreviewProps {
  visualQuery: VisualQuery
}

export function VisualQueryPreview({ visualQuery }: VisualQueryPreviewProps) {
  const { when, where, condition, action } = visualQuery

  const sections = [
    {
      icon: <IconClock size={16} />,
      label: 'When',
      value: when,
      color: 'blue',
    },
    {
      icon: <IconMapPin size={16} />,
      label: 'Where',
      value: where,
      color: 'cyan',
    },
    {
      icon: <IconFilter size={16} />,
      label: 'Condition',
      value: condition,
      color: 'orange',
    },
    {
      icon: <IconBell size={16} />,
      label: 'Action',
      value: action,
      color: 'green',
    },
  ]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Card radius="md" p="lg" withBorder>
        <Stack spacing="md">
          <Group justify="space-between">
            <Group spacing="xs">
              <ThemeIcon size="sm" radius="xl" variant="light" color="blue">
                <IconEye size={16} />
              </ThemeIcon>
              <Text size="sm" fw={600}>Live Preview</Text>
            </Group>
            <Badge size="sm" variant="light" color="green" leftSection={<IconCheck size={12} />}>
              Ready to activate
            </Badge>
          </Group>

          <Box
            p="md"
            style={{
              backgroundColor: 'var(--mantine-color-gray-0)',
              borderRadius: 8,
              border: '1px dashed var(--mantine-color-gray-3)',
            }}
          >
            <Stack spacing="xs">
              <Text size="xs" c="dimmed" fw={500} tt="uppercase" style={{ letterSpacing: 1 }}>
                Your Alert Will:
              </Text>
              
              <Stack spacing="lg">
                {sections.map((section, index) => (
                  <motion.div
                    key={section.label}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    <Group gap="md" style={{ flexWrap: 'nowrap' }}>
                      <ThemeIcon
                        size="md"
                        radius="xl"
                        variant="light"
                        color={section.color}
                      >
                        {section.icon}
                      </ThemeIcon>
                      <Box style={{ flex: 1 }}>
                        <Text size="xs" c="dimmed" fw={500}>
                          {section.label}
                        </Text>
                        <Text size="sm" fw={600} mt={2}>
                          {section.value}
                        </Text>
                      </Box>
                    </Group>
                    {index < sections.length - 1 && (
                      <Divider 
                        mt="md" 
                        variant="dashed" 
                        style={{ marginLeft: 44 }}
                      />
                    )}
                  </motion.div>
                ))}
              </Stack>
            </Stack>
          </Box>

          {/* Natural Language Summary */}
          <Box
            p="sm"
            style={{
              backgroundColor: 'var(--mantine-color-blue-0)',
              borderRadius: 6,
              border: '1px solid var(--mantine-color-blue-2)',
            }}
          >
            <Group spacing="xs">
              <IconCheck size={16} style={{ color: 'var(--mantine-color-blue-6)' }} />
              <Text size="sm" c="blue" fw={500}>
                Alert Summary
              </Text>
            </Group>
            <Text size="sm" mt="xs">
              Monitor {when.toLowerCase()} {where.toLowerCase()} when {condition.toLowerCase()}, 
              then send {action.toLowerCase()}.
            </Text>
          </Box>

          {/* Estimated Trigger Frequency */}
          <Group justify="space-between" px="xs">
            <Text size="xs" c="dimmed">
              Estimated trigger frequency:
            </Text>
            <Badge size="sm" variant="dot" color="orange">
              2-3 times per week
            </Badge>
          </Group>
        </Stack>
      </Card>
    </motion.div>
  )
}
