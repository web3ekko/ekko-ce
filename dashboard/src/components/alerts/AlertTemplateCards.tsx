/**
 * Alert Template Cards Component
 *
 * Displays vNext AlertTemplates in a card grid layout.
 */

import {
  Card,
  Grid,
  Group,
  Stack,
  Text,
  Button,
  Badge,
  Center,
  ThemeIcon,
} from '@mantine/core'
import {
  IconTemplate,
  IconWallet,
  IconCoins,
  IconShieldCheck,
  IconActivity,
  IconNetwork,
  IconCertificate,
} from '@tabler/icons-react'
import type { AlertTemplateSummary } from '../../services/alerts-api'

interface AlertTemplateCardsProps {
  templates: AlertTemplateSummary[]
  isLoading?: boolean
  onUseTemplate?: (template: AlertTemplateSummary) => void
  onViewTemplate?: (template: AlertTemplateSummary) => void
}

const TEMPLATE_META: Record<string, { label: string; icon: typeof IconTemplate; color: string }> = {
  wallet: { label: 'Wallet', icon: IconWallet, color: 'blue' },
  token: { label: 'Token', icon: IconCoins, color: 'teal' },
  contract: { label: 'Contract', icon: IconShieldCheck, color: 'orange' },
  protocol: { label: 'Protocol', icon: IconNetwork, color: 'grape' },
  network: { label: 'Network', icon: IconNetwork, color: 'green' },
  anomaly: { label: 'Anomaly', icon: IconActivity, color: 'red' },
}

const getTemplateMeta = (template: AlertTemplateSummary) => {
  const key = (template.target_kind || '').toLowerCase()
  return TEMPLATE_META[key] || { label: 'Template', icon: IconTemplate, color: 'gray' }
}

export function AlertTemplateCards({
  templates,
  isLoading = false,
  onUseTemplate,
  onViewTemplate,
}: AlertTemplateCardsProps) {
  if (isLoading) {
    return (
      <Center h={240}>
        <Stack align="center" gap="xs">
          <Text size="sm" c="dimmed">
            Loading templates...
          </Text>
        </Stack>
      </Center>
    )
  }

  if (templates.length === 0) {
    return (
      <Center h={240}>
        <Stack align="center" gap="xs">
          <ThemeIcon size="lg" variant="light" color="gray">
            <IconTemplate size={20} />
          </ThemeIcon>
          <Text size="sm" c="dimmed">
            No templates available yet.
          </Text>
        </Stack>
      </Center>
    )
  }

  return (
    <Grid>
      {templates.map((template) => {
        const meta = getTemplateMeta(template)
        const MetaIcon = meta.icon
        return (
          <Grid.Col key={template.id} span={{ base: 12, sm: 6, md: 4 }}>
            <Card
              shadow="sm"
              padding="lg"
              radius="md"
              withBorder
              style={{
                cursor: onViewTemplate ? 'pointer' : 'default',
                height: '100%',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
              }}
              onClick={() => onViewTemplate?.(template)}
            >
              <Stack gap="sm" h="100%">
                <Group justify="space-between" align="flex-start">
                  <Group gap="xs">
                    <ThemeIcon size="lg" radius="md" variant="light" color={meta.color}>
                      <MetaIcon size={20} />
                    </ThemeIcon>
                    <div>
                      <Text size="sm" fw={600} c="#0F172A">
                        {template.name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {meta.label}
                      </Text>
                    </div>
                  </Group>
                  <Group gap={4}>
                    {template.is_verified && (
                      <Badge size="xs" color="blue" variant="light" leftSection={<IconCertificate size={12} />}>
                        Verified
                      </Badge>
                    )}
                    {template.is_public && (
                      <Badge size="xs" variant="outline" color="gray">
                        Public
                      </Badge>
                    )}
                  </Group>
                </Group>

                <Text size="sm" c="dimmed" lineClamp={3}>
                  {template.description || 'No description provided.'}
                </Text>

                <Group gap="xs">
                  <Badge size="xs" variant="light" color="gray">
                    {template.usage_count} uses
                  </Badge>
                  {template.scope_networks?.[0] && (
                    <Badge size="xs" variant="light" color="gray">
                      {template.scope_networks[0]}
                    </Badge>
                  )}
                  {template.created_by_email && (
                    <Badge size="xs" variant="outline" color="gray">
                      {template.created_by_email}
                    </Badge>
                  )}
                </Group>

                <Group justify="space-between" mt="auto">
                  {onViewTemplate && (
                    <Button
                      size="xs"
                      variant="light"
                      onClick={(event) => {
                        event.stopPropagation()
                        onViewTemplate(template)
                      }}
                    >
                      View details
                    </Button>
                  )}
                  {onUseTemplate && (
                    <Button
                      size="xs"
                      onClick={(event) => {
                        event.stopPropagation()
                        onUseTemplate(template)
                      }}
                    >
                      Use template
                    </Button>
                  )}
                </Group>
              </Stack>
            </Card>
          </Grid.Col>
        )
      })}
    </Grid>
  )
}
