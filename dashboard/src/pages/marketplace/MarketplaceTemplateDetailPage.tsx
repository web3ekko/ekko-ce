/**
 * Marketplace Template Detail Page
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Divider,
  Group,
  Loader,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import {
  IconAlertCircle,
  IconArrowLeft,
  IconTemplate,
  IconWallet,
  IconCoins,
  IconShieldCheck,
  IconActivity,
  IconNetwork,
} from '@tabler/icons-react'
import { useNavigate, useParams } from 'react-router-dom'
import { notifications } from '@mantine/notifications'
import { alertsApiService, type AlertTemplateSummary } from '../../services/alerts-api'

const TEMPLATE_META: Record<string, { label: string; icon: typeof IconTemplate; color: string }> = {
  wallet: { label: 'Wallet', icon: IconWallet, color: 'blue' },
  token: { label: 'Token', icon: IconCoins, color: 'teal' },
  contract: { label: 'Contract', icon: IconShieldCheck, color: 'orange' },
  protocol: { label: 'Protocol', icon: IconNetwork, color: 'grape' },
  network: { label: 'Network', icon: IconNetwork, color: 'green' },
  anomaly: { label: 'Anomaly', icon: IconActivity, color: 'red' },
}

export function MarketplaceTemplateDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [template, setTemplate] = useState<(AlertTemplateSummary & { latest_template_version?: number }) | null>(null)
  const [templateVersion, setTemplateVersion] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isActive = true

    const loadTemplate = async () => {
      if (!id) return
      setIsLoading(true)
      setError(null)
      try {
        const resp = await alertsApiService.getTemplateLatest(id)
        if (!isActive) return
        if (!resp.success || !resp.template || !resp.bundle) {
          setError(resp.message || 'Unable to load template')
          return
        }
        setTemplate(resp.template as any)
        setTemplateVersion(resp.bundle.template_version)
      } catch (loadError: any) {
        console.error('Failed to load template:', loadError)
        if (isActive) {
          setError(loadError?.message || 'Unable to load template')
        }
      } finally {
        if (isActive) setIsLoading(false)
      }
    }

    loadTemplate()
    return () => {
      isActive = false
    }
  }, [id])

  const meta = useMemo(() => {
    if (!template) return null
    const key = (template.target_kind || '').toLowerCase()
    return TEMPLATE_META[key] || { label: 'Template', icon: IconTemplate, color: 'gray' }
  }, [template])

  const handleUseTemplate = () => {
    if (!template || !templateVersion) return
    notifications.show({
      title: 'Template selected',
      message: 'Opening the alert builder with this template.',
      color: 'blue',
      icon: <IconTemplate size={16} />,
    })
    navigate(`/dashboard/alerts?create=true&template_id=${template.id}&template_version=${templateVersion}`)
  }

  if (isLoading) {
    return (
      <Center h={300}>
        <Loader size="lg" />
      </Center>
    )
  }

  if (error || !template || !templateVersion) {
    return (
      <Container size="md" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
          {error || 'Template not found'}
        </Alert>
        <Button
          mt="md"
          variant="light"
          leftSection={<IconArrowLeft size={16} />}
          onClick={() => navigate('/dashboard/marketplace')}
        >
          Back to marketplace
        </Button>
      </Container>
    )
  }

  const MetaIcon = meta?.icon || IconTemplate

  return (
    <Container size="md" py="xl">
      <Stack gap="lg">
        <Button variant="subtle" leftSection={<IconArrowLeft size={16} />} onClick={() => navigate('/dashboard/marketplace')}>
          Back to marketplace
        </Button>

        <Card withBorder radius="md" padding="lg">
          <Stack gap="md">
            <Group justify="space-between" align="flex-start">
              <Group gap="sm">
                <ThemeIcon size="lg" radius="md" variant="light" color={meta?.color || 'gray'}>
                  <MetaIcon size={20} />
                </ThemeIcon>
                <div>
                  <Title order={3}>{template.name}</Title>
                  <Group gap="xs" mt={4}>
                    <Badge size="sm" color={meta?.color || 'gray'} variant="light">
                      {meta?.label || 'Template'}
                    </Badge>
                    {template.is_verified && (
                      <Badge size="sm" color="blue" variant="light">
                        Verified
                      </Badge>
                    )}
                    {template.is_public && (
                      <Badge size="sm" variant="outline">
                        Public
                      </Badge>
                    )}
                    <Badge size="sm" variant="light" color="gray">
                      v{templateVersion}
                    </Badge>
                  </Group>
                </div>
              </Group>
              <Button onClick={handleUseTemplate}>Use template</Button>
            </Group>

            <Text c="dimmed">
              {template.description || 'No description provided.'}
            </Text>

            <Divider />

            <Group gap="md">
              <Badge size="sm" variant="light" color="gray">
                {template.usage_count} uses
              </Badge>
              {template.scope_networks?.[0] && (
                <Badge size="sm" variant="light" color="gray">
                  {template.scope_networks[0]}
                </Badge>
              )}
              {template.created_by_email && (
                <Badge size="sm" variant="outline" color="gray">
                  {template.created_by_email}
                </Badge>
              )}
            </Group>

            <Stack gap="xs">
              <Text size="sm" fw={600}>Template variables</Text>
              {template.variable_names?.length ? (
                <Group gap="xs">
                  {template.variable_names.map((variable) => (
                    <Badge key={variable} size="sm" variant="light" color="gray">
                      {variable}
                    </Badge>
                  ))}
                </Group>
              ) : (
                <Text size="sm" c="dimmed">
                  No variables required.
                </Text>
              )}
            </Stack>
          </Stack>
        </Card>
      </Stack>
    </Container>
  )
}
