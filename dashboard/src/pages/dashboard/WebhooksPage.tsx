import {
  Container,
  Title,
  Text,
  Button,
  Card,
  Stack,
  Group,
  Badge,
  SimpleGrid,
  ActionIcon,
  Menu,
  TextInput,
  Alert,
  Center,
  Loader,
} from '@mantine/core'
import {
  IconPlus,
  IconDotsVertical,
  IconPlugConnected,
  IconExternalLink,
  IconTrash,
  IconEdit,
  IconSearch,
  IconAlertCircle,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ConfigureWebhookModal } from '../../components/notifications/ConfigureWebhookModal'
import { notificationsApiService, type NotificationChannelEndpoint, type WebhookChannelConfig } from '../../services/notifications-api'

const formatLastUsed = (value?: string) => {
  if (!value) return 'Never'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return date.toLocaleString()
}

export function WebhooksPage() {
  const [modalOpen, setModalOpen] = useState(false)
  const [activeWebhook, setActiveWebhook] = useState<NotificationChannelEndpoint | null>(null)
  const [webhooks, setWebhooks] = useState<NotificationChannelEndpoint[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const loadWebhooks = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await notificationsApiService.getChannels({ channel_type: 'webhook' })
      setWebhooks(response.results || [])
    } catch (loadError: any) {
      console.error('Failed to load webhook channels:', loadError)
      setError(loadError?.message || 'Unable to load webhook channels.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWebhooks()
  }, [loadWebhooks])

  const filteredWebhooks = useMemo(() => {
    const normalized = search.trim().toLowerCase()
    if (!normalized) return webhooks

    return webhooks.filter((webhook) => {
      const config = webhook.config as WebhookChannelConfig
      return (
        webhook.label.toLowerCase().includes(normalized) ||
        config?.url?.toLowerCase().includes(normalized)
      )
    })
  }, [search, webhooks])

  const openCreateModal = () => {
    setActiveWebhook(null)
    setModalOpen(true)
  }

  const openEditModal = (webhook: NotificationChannelEndpoint) => {
    setActiveWebhook(webhook)
    setModalOpen(true)
  }

  const handleTestWebhook = async (webhook: NotificationChannelEndpoint) => {
    try {
      const response = await notificationsApiService.testChannel(webhook.id)
      notifications.show({
        title: response.success ? 'Test payload sent' : 'Test failed',
        message: response.message || 'Webhook test completed.',
        color: response.success ? 'teal' : 'red',
        icon: <IconExternalLink size={16} />,
      })
    } catch (testError: any) {
      notifications.show({
        title: 'Webhook test failed',
        message: testError?.message || 'Unable to send test payload.',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  const handleDeleteWebhook = async (webhook: NotificationChannelEndpoint) => {
    const confirmed = window.confirm(`Delete webhook "${webhook.label}"? This cannot be undone.`)
    if (!confirmed) return

    try {
      await notificationsApiService.deleteChannel(webhook.id)
      notifications.show({
        title: 'Webhook deleted',
        message: 'The webhook endpoint has been removed.',
        color: 'green',
      })
      loadWebhooks()
    } catch (deleteError: any) {
      notifications.show({
        title: 'Delete failed',
        message: deleteError?.message || 'Unable to delete webhook.',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  const emptyState = !isLoading && filteredWebhooks.length === 0

  return (
    <Container fluid px={0}>
      <Group justify="space-between" mb="xl">
        <Stack gap={4}>
          <Title order={2}>Webhooks</Title>
          <Text c="dimmed" size="sm">
            Manage webhook endpoints for programmatic alert delivery
          </Text>
        </Stack>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={openCreateModal}
          style={{ backgroundColor: '#0F172A' }}
        >
          Add Webhook
        </Button>
      </Group>

      <TextInput
        placeholder="Search webhooks..."
        leftSection={<IconSearch size={16} />}
        mb="lg"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />

      {error && (
        <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light" mb="lg">
          {error}
        </Alert>
      )}

      {isLoading ? (
        <Center h={240}>
          <Loader size="sm" />
        </Center>
      ) : emptyState ? (
        <Center h={240}>
          <Stack align="center" gap="xs">
            <IconPlugConnected size={32} color="#64748B" />
            <Text fw={600} size="sm">No webhook endpoints yet</Text>
            <Text size="xs" c="dimmed" ta="center" maw={280}>
              Add a webhook endpoint to receive real-time alert payloads in your systems.
            </Text>
            <Button size="xs" variant="light" onClick={openCreateModal}>
              Configure webhook
            </Button>
          </Stack>
        </Center>
      ) : (
        <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="lg">
          {filteredWebhooks.map((webhook) => {
            const config = webhook.config as WebhookChannelConfig
            return (
              <Card key={webhook.id} withBorder radius="md" p="md">
                <Stack gap="md">
                  <Group justify="space-between" align="flex-start">
                    <Group gap="xs">
                      <IconPlugConnected size={20} color="#3B82F6" />
                      <Text fw={600} size="lg">{webhook.label}</Text>
                    </Group>
                    <Menu position="bottom-end" shadow="md">
                      <Menu.Target>
                        <ActionIcon variant="subtle" color="gray">
                          <IconDotsVertical size={16} />
                        </ActionIcon>
                      </Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item leftSection={<IconEdit size={14} />} onClick={() => openEditModal(webhook)}>
                          Edit Configuration
                        </Menu.Item>
                        <Menu.Item
                          leftSection={<IconExternalLink size={14} />}
                          onClick={() => handleTestWebhook(webhook)}
                        >
                          Test Payload
                        </Menu.Item>
                        <Menu.Divider />
                        <Menu.Item
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          onClick={() => handleDeleteWebhook(webhook)}
                        >
                          Delete
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Group>

                  <Group gap="xs">
                    <Badge
                      color={webhook.enabled ? 'green' : 'gray'}
                      variant="light"
                      size="sm"
                    >
                      {webhook.enabled ? 'active' : 'disabled'}
                    </Badge>
                    {webhook.verified && (
                      <Badge color="blue" variant="light" size="sm">
                        verified
                      </Badge>
                    )}
                    <Badge color="gray" variant="light" size="sm">
                      {config?.method || 'POST'}
                    </Badge>
                  </Group>

                  <Stack gap={4}>
                    <Text size="xs" fw={500} c="dimmed">ENDPOINT URL</Text>
                    <Text
                      size="sm"
                      c="dimmed"
                      style={{
                        fontFamily: 'monospace',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '100%'
                      }}
                    >
                      {config?.url || 'N/A'}
                    </Text>
                  </Stack>

                  <Group gap="xs" justify="space-between">
                    <Text size="xs" c="dimmed">Last used: {formatLastUsed(webhook.last_used_at)}</Text>
                    <Button
                      variant="outline"
                      size="xs"
                      leftSection={<IconExternalLink size={14} />}
                      onClick={() => handleTestWebhook(webhook)}
                    >
                      Test
                    </Button>
                  </Group>
                </Stack>
              </Card>
            )
          })}
        </SimpleGrid>
      )}

      <ConfigureWebhookModal
        opened={modalOpen}
        onClose={() => setModalOpen(false)}
        channel={activeWebhook}
        onSaved={() => loadWebhooks()}
      />
    </Container>
  )
}
