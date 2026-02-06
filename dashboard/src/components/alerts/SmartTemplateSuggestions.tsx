/**
 * Smart Template Suggestions Component
 * 
 * Context-aware template recommendations with one-click application
 */

import { Stack, Group, Text, Card, Badge, ActionIcon, Box, Tooltip, ScrollArea, ThemeIcon } from '@mantine/core'
import {
  IconSparkles,
  IconUsers,
  IconCheck,
  IconChevronRight,
  IconWallet,
  IconTransferOut,
  IconGasStation,
  IconActivityHeartbeat,
  IconFileCode,
  IconPhoto,
  IconTemplate,
} from '@tabler/icons-react'
import { motion } from 'framer-motion'
import type { Template } from './CreateAlertOptimized'

interface SmartTemplateSuggestionsProps {
  templates: Template[]
  selectedTemplate?: Template
  onSelectTemplate: (template: Template) => void
}

type TemplateMeta = {
  label: string
  icon: typeof IconWallet
  color: string
}

const TEMPLATE_META: Record<string, TemplateMeta> = {
  wallet: { label: 'Wallet', icon: IconWallet, color: 'blue' },
  token: { label: 'Token', icon: IconTransferOut, color: 'teal' },
  contract: { label: 'Contract', icon: IconFileCode, color: 'cyan' },
  protocol: { label: 'Protocol', icon: IconGasStation, color: 'orange' },
  network: { label: 'Network', icon: IconActivityHeartbeat, color: 'teal' },
  anomaly: { label: 'Anomaly', icon: IconPhoto, color: 'orange' },
}

const DEFAULT_TEMPLATE_META: TemplateMeta = {
  label: 'Template',
  icon: IconTemplate,
  color: 'gray',
}

const getTemplateMeta = (template: Template): TemplateMeta => {
  const key = (template.templateType || template.eventType || '').toLowerCase()
  return TEMPLATE_META[key] || DEFAULT_TEMPLATE_META
}

export function SmartTemplateSuggestions({
  templates,
  selectedTemplate,
  onSelectTemplate,
}: SmartTemplateSuggestionsProps) {
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, x: -20 },
    show: { opacity: 1, x: 0 },
  }

  return (
    <Card radius="md" p="lg" withBorder>
      <Stack spacing="md">
        <Group justify="space-between">
          <Group gap="xs">
            <IconSparkles size={20} style={{ color: 'var(--mantine-color-teal-6)' }} />
            <Text size="sm" fw={600}>Smart Template Suggestions</Text>
          </Group>
          <Badge size="sm" variant="light" color="teal">
            {templates.length} matches
          </Badge>
        </Group>

        <ScrollArea.Autosize maxHeight={300}>
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
          >
            <Stack spacing="sm">
              {templates.map((template) => (
                <motion.div key={template.id} variants={item}>
                  <TemplateCard
                    template={template}
                    isSelected={selectedTemplate?.id === template.id}
                    onSelect={() => onSelectTemplate(template)}
                  />
                </motion.div>
              ))}
            </Stack>
          </motion.div>
        </ScrollArea.Autosize>
      </Stack>
    </Card>
  )
}

interface TemplateCardProps {
  template: Template
  isSelected: boolean
  onSelect: () => void
}

function TemplateCard({ template, isSelected, onSelect }: TemplateCardProps) {
  const meta = getTemplateMeta(template)
  const MetaIcon = meta.icon

  return (
    <Card
      p="md"
      radius="sm"
      withBorder
      style={{
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        borderColor: isSelected ? 'var(--mantine-color-blue-5)' : undefined,
        backgroundColor: isSelected ? 'var(--mantine-color-blue-0)' : undefined,
      }}
      onClick={onSelect}
    >
      <Group justify="space-between" style={{ flexWrap: 'nowrap' }}>
        <Group gap="sm" style={{ flex: 1, flexWrap: 'nowrap' }}>
          {/* Template Icon */}
          <ThemeIcon size="lg" radius="md" variant="light" color={meta.color}>
            <MetaIcon size={18} />
          </ThemeIcon>

          {/* Template Details */}
          <Box style={{ flex: 1 }}>
            <Group gap="xs">
              <Text size="sm" fw={600}>{template.name}</Text>
              {template.relevance >= 90 && (
        <Tooltip label="Best match for your description">
          <Badge size="xs" color="green" variant="light">
            Best Match
          </Badge>
        </Tooltip>
      )}
            </Group>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {template.description}
            </Text>
            <Group gap={4} mt={4}>
              <IconUsers size={12} style={{ opacity: 0.5 }} />
              <Text size="xs" c="dimmed">
                {template.usage.toLocaleString()} uses
              </Text>
              <Text size="xs" c="dimmed">•</Text>
              <Text size="xs" c={template.relevance >= 90 ? 'green' : 'dimmed'} fw={500}>
                {template.relevance}% match
              </Text>
            </Group>
          </Box>
        </Group>

        {/* Action Button */}
        <Group gap="xs">
          {isSelected && (
            <ThemeIcon size="sm" radius="xl" color="green" variant="light">
              <IconCheck size={14} />
            </ThemeIcon>
          )}
          <ActionIcon size="sm" variant="subtle">
            <IconChevronRight size={16} />
          </ActionIcon>
        </Group>
      </Group>

      {/* Hover Preview */}
      <motion.div
        initial={false}
        animate={{ height: isSelected ? 'auto' : 0 }}
        transition={{ duration: 0.2 }}
        style={{ overflow: 'hidden' }}
      >
        {isSelected && (
          <Box mt="md" pt="md" style={{ borderTop: '1px solid var(--mantine-color-gray-2)' }}>
            <Text size="xs" fw={500} mb={4}>Template Variables:</Text>
            {template.variableNames.length > 0 ? (
              <Group gap="xs">
                {template.variableNames.slice(0, 6).map((variable) => (
                  <Badge key={variable} size="xs" variant="outline">
                    {variable}
                  </Badge>
                ))}
              </Group>
            ) : (
              <Text size="xs" c="dimmed">No variables required.</Text>
            )}
          </Box>
        )}
      </motion.div>
    </Card>
  )
}
