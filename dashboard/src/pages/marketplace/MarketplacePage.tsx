/**
 * Marketplace Page
 *
 * Browse alert templates published to the marketplace or shared with your org.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Container,
  Title,
  Text,
  Group,
  Stack,
  TextInput,
  Select,
  Badge,
  Alert,
  Button,
} from '@mantine/core'
import { IconSearch, IconAlertCircle, IconTemplate } from '@tabler/icons-react'
import { useDebouncedValue } from '@mantine/hooks'
import { useNavigate } from 'react-router-dom'
import { notifications } from '@mantine/notifications'
import { alertsApiService, type AlertTemplateSummary } from '../../services/alerts-api'
import { AlertTemplateCards } from '../../components/alerts/AlertTemplateCards'

const SORT_OPTIONS = [
  { value: '-usage_count', label: 'Most used' },
  { value: '-created_at', label: 'Newest' },
  { value: 'name', label: 'Name (A-Z)' },
]

export function MarketplacePage() {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<AlertTemplateSummary[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTargetKind, setSelectedTargetKind] = useState('')
  const [ordering, setOrdering] = useState('-usage_count')
  const [debouncedQuery] = useDebouncedValue(searchQuery, 300)

  useEffect(() => {
    let isActive = true

    const loadMarketplace = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const response = await alertsApiService.listTemplates({
          search: debouncedQuery || undefined,
          target_kind: selectedTargetKind || undefined,
          ordering,
          page_size: 30,
        })
        if (!isActive) return
        setTemplates(response.results || [])
        if (!isActive) return
      } catch (loadError: any) {
        console.error('Failed to load marketplace items:', loadError)
        if (isActive) {
          setError(loadError?.message || 'Unable to load marketplace templates')
        }
      } finally {
        if (isActive) {
          setIsLoading(false)
        }
      }
    }

    loadMarketplace()

    return () => {
      isActive = false
    }
  }, [debouncedQuery, ordering, selectedTargetKind])

  const statsLabel = useMemo(() => {
    if (isLoading) return 'Loading templates'
    if (templates.length === 0) return 'No templates found'
    return `${templates.length} templates available`
  }, [isLoading, templates.length])

  const handleUseTemplate = (template: AlertTemplateSummary) => {
    notifications.show({
      title: 'Template ready',
      message: 'Opening the alert builder with this template.',
      color: 'blue',
      icon: <IconTemplate size={16} />,
    })
    navigate(`/dashboard/alerts?create=true&template_id=${template.id}&template_version=${template.latest_template_version}`)
  }

  const handleViewTemplate = (template: AlertTemplateSummary) => {
    navigate(`/dashboard/marketplace/templates/${template.id}`)
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <div>
            <Title order={2}>Marketplace</Title>
            <Text c="dimmed" mt={4}>
              Explore alert plans curated for monitoring wallets, protocols, and networks.
            </Text>
          </div>
          <Badge size="lg" color="blue" variant="light">
            {statsLabel}
          </Badge>
        </Group>

        <Group gap="sm" align="flex-end" wrap="wrap">
            <TextInput
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.currentTarget.value)}
              placeholder="Search templates..."
              leftSection={<IconSearch size={16} />}
              style={{ flex: 1, minWidth: 240 }}
            />
          <Select
            data={[
              { value: '', label: 'All target kinds' },
              { value: 'wallet', label: 'Wallet' },
              { value: 'token', label: 'Token' },
              { value: 'contract', label: 'Contract' },
              { value: 'protocol', label: 'Protocol' },
              { value: 'network', label: 'Network' },
            ]}
            value={selectedTargetKind}
            onChange={(value) => setSelectedTargetKind(value || '')}
            placeholder="Target kind"
            style={{ minWidth: 200 }}
            clearable
          />
          <Select
            data={SORT_OPTIONS}
            value={ordering}
            onChange={(value) => setOrdering(value || '-usage_count')}
            placeholder="Sort"
            style={{ minWidth: 160 }}
          />
          <Button variant="light" onClick={() => navigate('/dashboard/alerts')}
          >
            Create alert
          </Button>
        </Group>

          {error && (
          <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
            {error}
          </Alert>
        )}

        <AlertTemplateCards
          templates={templates}
          isLoading={isLoading}
          onUseTemplate={handleUseTemplate}
          onViewTemplate={handleViewTemplate}
        />
      </Stack>
    </Container>
  )
}
