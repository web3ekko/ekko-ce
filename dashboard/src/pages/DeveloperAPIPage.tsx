/**
 * Developer API Page
 * 
 * Comprehensive API management interface for developers
 */

import { useEffect, useState } from 'react'
import {
  Container,
  Title,
  Button,
  Grid,
  Card,
  Text,
  Group,
  Stack,
  Badge,
  Table,
  ActionIcon,
  Menu,
  Tabs,
  Select,
  TextInput,
  Textarea,
  JsonInput,
  Code,
  Alert,
  Indicator,
  Tooltip,
  Modal,
  NumberInput,
  Switch,
  MultiSelect,
  Divider,
  Paper,
  ScrollArea
} from '@mantine/core'
import {
  IconKey,
  IconPlus,
  IconTrendingUp,
  IconTrendingDown,
  IconWebhook,
  IconAlertCircle,
  IconCheck,
  IconCopy,
  IconEdit,
  IconTrash,
  IconDots,
  IconPlayerPlay,
  IconCode,
  IconSettings,
  IconRefresh,
  IconExternalLink,
  IconDownload,
  IconEye,
  IconEyeOff
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useDisclosure } from '@mantine/hooks'
import { useApiManagementStore } from '../store/api-management'

export function DeveloperAPIPage() {
  const {
    apiKeys,
    webhooks,
    usage,
    endpoints,
    isLoading,
    error,
    selectedEndpoint,
    testRequest,
    testResponse,
    loadApiKeys,
    loadWebhooks,
    loadUsage,
    loadEndpoints,
    createApiKey,
    deleteApiKey,
    revokeApiKey,
    createWebhook,
    deleteWebhook,
    testWebhook,
    setSelectedEndpoint,
    updateTestRequest,
    executeApiTest,
    clearTestResponse
  } = useApiManagementStore()

  const [createKeyOpened, { open: openCreateKey, close: closeCreateKey }] = useDisclosure(false)
  const [createWebhookOpened, { open: openCreateWebhook, close: closeCreateWebhook }] = useDisclosure(false)
  const [activeTab, setActiveTab] = useState<string | null>('overview')

  // Load data on mount
  useEffect(() => {
    loadApiKeys()
    loadWebhooks()
    loadUsage()
    loadEndpoints()
  }, [])

  // Calculate overview stats
  const totalApiCalls = usage.reduce((sum, day) => sum + day.requests, 0)
  const totalErrors = usage.reduce((sum, day) => sum + day.errors, 0)
  const errorRate = totalApiCalls > 0 ? (totalErrors / totalApiCalls) * 100 : 0
  const activeWebhooks = webhooks.filter(w => w.status === 'connected').length

  // Get trend for API calls (compare last 3 days vs previous 3 days)
  const recentCalls = usage.slice(-3).reduce((sum, day) => sum + day.requests, 0)
  const previousCalls = usage.slice(-6, -3).reduce((sum, day) => sum + day.requests, 0)
  const callsTrend = previousCalls > 0 ? ((recentCalls - previousCalls) / previousCalls) * 100 : 0

  const handleCopyApiKey = (keyId: string) => {
    navigator.clipboard.writeText(keyId)
    notifications.show({
      title: 'Copied!',
      message: 'API key copied to clipboard',
      color: 'green',
      icon: <IconCopy size={16} />
    })
  }

  const handleCreateApiKey = async (formData: any) => {
    try {
      const rawKey = await createApiKey({
        name: formData.name,
        access_level: formData.access_level,
        expires_at: formData.expires_at,
        rate_limit: {
          requests_per_minute: formData.rate_limit_minute,
          requests_per_day: formData.rate_limit_day,
        },
      })

      await navigator.clipboard.writeText(rawKey)

      notifications.show({
        title: 'API Key Created',
        message: 'Your new API key has been copied to the clipboard.',
        color: 'green',
        icon: <IconCheck size={16} />
      })

      closeCreateKey()
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to create API key',
        color: 'red',
        icon: <IconAlertCircle size={16} />
      })
    }
  }

  const handleDeleteApiKey = async (id: string) => {
    try {
      await deleteApiKey(id)
      notifications.show({
        title: 'API Key Deleted',
        message: 'API key has been permanently deleted',
        color: 'orange',
        icon: <IconTrash size={16} />
      })
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to delete API key',
        color: 'red'
      })
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'green'
      case 'expires_soon': return 'yellow'
      case 'expired': return 'red'
      case 'revoked': return 'gray'
      default: return 'blue'
    }
  }

  const getWebhookStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'green'
      case 'disconnected': return 'gray'
      case 'error': return 'red'
      default: return 'blue'
    }
  }

  return (
    <Container size="xl" py="md">
      <Group justify="space-between" mb="xl">
        <Title order={1}>Developer API</Title>
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={openCreateKey}
        >
          Create API Key
        </Button>
      </Group>

      {error && (
        <Alert
          icon={<IconAlertCircle size={16} />}
          title="Error"
          color="red"
          mb="md"
        >
          {error}
        </Alert>
      )}

      <Tabs value={activeTab} onChange={setActiveTab}>
        <Tabs.List>
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="keys">API Keys</Tabs.Tab>
          <Tabs.Tab value="tester">API Tester</Tabs.Tab>
          <Tabs.Tab value="webhooks">Webhooks</Tabs.Tab>
          <Tabs.Tab value="docs">Documentation</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          {/* Overview Cards */}
          <Grid mb="xl">
            <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <Card
                padding="md"
                radius="md"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E6E9EE',
                  borderLeft: '4px solid #2563EB',
                }}
              >
                <Group gap="xs">
                  <IconKey size={20} color="#2563EB" />
                  <div>
                    <Text size="sm" c="#475569">Active API Keys</Text>
                    <Text size="xl" fw={700} c="#0F172A">{apiKeys.filter(k => k.status === 'active').length}</Text>
                  </div>
                </Group>
                <Text size="xs" c="#64748B" mt="xs">1 key expires in 14 days</Text>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <Card
                padding="md"
                radius="md"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E6E9EE',
                  borderLeft: '4px solid #10B981',
                }}
              >
                <Group gap="xs">
                  <IconCode size={20} color="#10B981" />
                  <div>
                    <Text size="sm" c="#475569">API Calls (24h)</Text>
                    <Text size="xl" fw={700} c="#0F172A">{totalApiCalls.toLocaleString()}</Text>
                  </div>
                </Group>
                <Group gap={4} mt="xs">
                  {callsTrend > 0 ? (
                    <IconTrendingUp size={12} color="#10B981" />
                  ) : (
                    <IconTrendingDown size={12} color="#EF4444" />
                  )}
                  <Text size="xs" c={callsTrend > 0 ? '#10B981' : '#EF4444'}>
                    {Math.abs(callsTrend).toFixed(1)}% from yesterday
                  </Text>
                </Group>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <Card
                padding="md"
                radius="md"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E6E9EE',
                  borderLeft: '4px solid #14B8A6',
                }}
              >
                <Group gap="xs">
                  <IconWebhook size={20} color="#14B8A6" />
                  <div>
                    <Text size="sm" c="#475569">Webhooks</Text>
                    <Text size="xl" fw={700} c="#0F172A">{activeWebhooks}</Text>
                  </div>
                </Group>
                <Text size="xs" c="#64748B" mt="xs">All systems operational</Text>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, sm: 6, lg: 3 }}>
              <Card
                padding="md"
                radius="md"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E6E9EE',
                  borderLeft: '4px solid #F59E0B',
                }}
              >
                <Group gap="xs">
                  <IconAlertCircle size={20} color="#F59E0B" />
                  <div>
                    <Text size="sm" c="#475569">Error Rate</Text>
                    <Text size="xl" fw={700} c="#0F172A">{errorRate.toFixed(1)}%</Text>
                  </div>
                </Group>
                <Group gap={4} mt="xs">
                  <IconTrendingDown size={12} color="#10B981" />
                  <Text size="xs" c="#10B981">0.2% from last week</Text>
                </Group>
              </Card>
            </Grid.Col>
          </Grid>

          {/* Quick Actions */}
          <Card withBorder mb="xl">
            <Title order={3} mb="md">Quick Actions</Title>
            <Group>
              <Button
                variant="light"
                leftSection={<IconKey size={16} />}
                onClick={openCreateKey}
              >
                Create API Key
              </Button>
              <Button
                variant="light"
                leftSection={<IconWebhook size={16} />}
                onClick={openCreateWebhook}
              >
                Add Webhook
              </Button>
              <Button
                variant="light"
                leftSection={<IconCode size={16} />}
                onClick={() => setActiveTab('tester')}
              >
                Test API
              </Button>
              <Button
                variant="light"
                leftSection={<IconExternalLink size={16} />}
                component="a"
                href="#"
                target="_blank"
              >
                View Docs
              </Button>
            </Group>
          </Card>

          {/* Recent Activity */}
          <Card withBorder>
            <Title order={3} mb="md">Recent Activity</Title>
            <Stack gap="sm">
              <Group justify="space-between">
                <Text size="sm">Production Key used for wallet query</Text>
                <Text size="xs" c="dimmed">2 minutes ago</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">Webhook delivery successful</Text>
                <Text size="xs" c="dimmed">5 minutes ago</Text>
              </Group>
              <Group justify="space-between">
                <Text size="sm">New API key created: Testing Key</Text>
                <Text size="xs" c="dimmed">1 hour ago</Text>
              </Group>
            </Stack>
          </Card>
        </Tabs.Panel>

        <Tabs.Panel value="keys" pt="md">
          {/* API Keys Management */}
          <Card withBorder>
            <Group justify="space-between" mb="md">
              <Title order={3}>API Keys</Title>
              <Group>
                <Button
                  variant="light"
                  leftSection={<IconRefresh size={16} />}
                  onClick={loadApiKeys}
                  loading={isLoading}
                >
                  Refresh
                </Button>
                <Button
                  leftSection={<IconPlus size={16} />}
                  onClick={openCreateKey}
                >
                  New API Key
                </Button>
              </Group>
            </Group>

            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Key ID</Table.Th>
                  <Table.Th>Created</Table.Th>
                  <Table.Th>Expires</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {apiKeys.map((key) => (
                  <Table.Tr key={key.id}>
                    <Table.Td>
                      <div>
                        <Text fw={500}>{key.name}</Text>
                        <Text size="xs" c="dimmed">{key.access_level} access</Text>
                      </div>
                    </Table.Td>
                    <Table.Td>
                      <Group gap="xs">
                          <Code>{key.key_prefix}</Code>
                        <ActionIcon
                          variant="subtle"
                          size="sm"
                          onClick={() => handleCopyApiKey(key.key_prefix)}
                        >
                          <IconCopy size={14} />
                        </ActionIcon>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {new Date(key.created_at).toLocaleDateString()}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">
                        {key.expires_at
                          ? new Date(key.expires_at).toLocaleDateString()
                          : 'Never'
                        }
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={getStatusColor(key.status)} variant="light">
                        {key.status}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Menu shadow="md" width={200}>
                        <Menu.Target>
                          <ActionIcon variant="subtle">
                            <IconDots size={16} />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                          <Menu.Item leftSection={<IconEye size={14} />}>
                            View Details
                          </Menu.Item>
                          <Menu.Item leftSection={<IconEdit size={14} />}>
                            Edit
                          </Menu.Item>
                          <Menu.Item leftSection={<IconCopy size={14} />}>
                            Copy Key
                          </Menu.Item>
                          <Menu.Divider />
                          <Menu.Item
                            leftSection={<IconEyeOff size={14} />}
                            onClick={() => revokeApiKey(key.id)}
                          >
                            Revoke
                          </Menu.Item>
                          <Menu.Item
                            color="red"
                            leftSection={<IconTrash size={14} />}
                            onClick={() => handleDeleteApiKey(key.id)}
                          >
                            Delete
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Tabs.Panel>

        <Tabs.Panel value="tester" pt="md">
          <Grid>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Card withBorder>
                <Title order={3} mb="md">API Tester</Title>

                <Stack gap="md">
                  <Select
                    label="Endpoint"
                    placeholder="Select an endpoint to test"
                    value={selectedEndpoint}
                    onChange={setSelectedEndpoint}
                    data={endpoints.map(endpoint => ({
                      value: `${endpoint.method} ${endpoint.path}`,
                      label: `${endpoint.method} ${endpoint.path}`
                    }))}
                  />

                  <Group grow>
                    <Select
                      label="Method"
                      value={testRequest.method}
                      onChange={(value) => updateTestRequest({ method: value || 'GET' })}
                      data={['GET', 'POST', 'PUT', 'DELETE', 'PATCH']}
                    />
                  </Group>

                  <TextInput
                    label="URL"
                    value={testRequest.url}
                    onChange={(e) => updateTestRequest({ url: e.target.value })}
                    placeholder="https://api.ekko.com/v1/..."
                  />

                  <JsonInput
                    label="Headers"
                    value={JSON.stringify(testRequest.headers, null, 2)}
                    onChange={(value) => {
                      try {
                        const headers = JSON.parse(value)
                        updateTestRequest({ headers })
                      } catch (e) {
                        // Invalid JSON, ignore
                      }
                    }}
                    minRows={3}
                    maxRows={6}
                  />

                  {['POST', 'PUT', 'PATCH'].includes(testRequest.method) && (
                    <JsonInput
                      label="Request Body"
                      value={testRequest.body}
                      onChange={(value) => updateTestRequest({ body: value })}
                      minRows={4}
                      maxRows={10}
                      placeholder='{"key": "value"}'
                    />
                  )}

                  <Group>
                    <Button
                      leftSection={<IconPlayerPlay size={16} />}
                      onClick={executeApiTest}
                      loading={isLoading}
                    >
                      Send Request
                    </Button>
                    <Button
                      variant="light"
                      onClick={clearTestResponse}
                    >
                      Clear
                    </Button>
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Card withBorder>
                <Title order={3} mb="md">Response</Title>

                {testResponse ? (
                  <Stack gap="md">
                    {testResponse.status && (
                      <Group>
                        <Badge
                          color={testResponse.status < 400 ? 'green' : 'red'}
                          variant="light"
                        >
                          {testResponse.status}
                        </Badge>
                        <Text size="sm" c="dimmed">
                          {testResponse.status < 400 ? 'Success' : 'Error'}
                        </Text>
                      </Group>
                    )}

                    {testResponse.headers && (
                      <div>
                        <Text size="sm" fw={500} mb="xs">Headers:</Text>
                        <Code block>
                          {JSON.stringify(testResponse.headers, null, 2)}
                        </Code>
                      </div>
                    )}

                    <div>
                      <Text size="sm" fw={500} mb="xs">Response Body:</Text>
                      <ScrollArea.Autosize mah={400}>
                        <Code block>
                          {testResponse.error
                            ? testResponse.error
                            : JSON.stringify(testResponse.body, null, 2)
                          }
                        </Code>
                      </ScrollArea.Autosize>
                    </div>
                  </Stack>
                ) : (
                  <Text c="dimmed" ta="center" py="xl">
                    Send a request to see the response here
                  </Text>
                )}
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="webhooks" pt="md">
          <Grid>
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <Card withBorder>
                <Group justify="space-between" mb="md">
                  <Title order={3}>Webhook Notifications</Title>
                  <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={openCreateWebhook}
                  >
                    Add Webhook
                  </Button>
                </Group>

                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Name</Table.Th>
                      <Table.Th>URL</Table.Th>
                      <Table.Th>Events</Table.Th>
                      <Table.Th>Status</Table.Th>
                      <Table.Th>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {webhooks.map((webhook) => (
                      <Table.Tr key={webhook.id}>
                        <Table.Td>
                          <div>
                            <Text fw={500}>{webhook.name}</Text>
                            <Text size="xs" c="dimmed">
                              {webhook.delivery_count} deliveries
                            </Text>
                          </div>
                        </Table.Td>
                        <Table.Td>
                          <Code>{webhook.url}</Code>
                        </Table.Td>
                        <Table.Td>
                          <Group gap={4}>
                            {webhook.events.slice(0, 2).map((event) => (
                              <Badge key={event} size="xs" variant="light">
                                {event}
                              </Badge>
                            ))}
                            {webhook.events.length > 2 && (
                              <Badge size="xs" variant="light" color="gray">
                                +{webhook.events.length - 2}
                              </Badge>
                            )}
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs">
                            <Indicator
                              color={getWebhookStatusColor(webhook.status)}
                              size={8}
                            />
                            <Badge
                              color={getWebhookStatusColor(webhook.status)}
                              variant="light"
                              size="sm"
                            >
                              {webhook.status}
                            </Badge>
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Menu shadow="md" width={200}>
                            <Menu.Target>
                              <ActionIcon variant="subtle">
                                <IconDots size={16} />
                              </ActionIcon>
                            </Menu.Target>
                            <Menu.Dropdown>
                              <Menu.Item
                                leftSection={<IconPlayerPlay size={14} />}
                                onClick={() => testWebhook(webhook.id)}
                              >
                                Test Webhook
                              </Menu.Item>
                              <Menu.Item leftSection={<IconEdit size={14} />}>
                                Edit
                              </Menu.Item>
                              <Menu.Item leftSection={<IconSettings size={14} />}>
                                Configure
                              </Menu.Item>
                              <Menu.Divider />
                              <Menu.Item
                                color="red"
                                leftSection={<IconTrash size={14} />}
                                onClick={() => deleteWebhook(webhook.id)}
                              >
                                Delete
                              </Menu.Item>
                            </Menu.Dropdown>
                          </Menu>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Card withBorder>
                <Title order={4} mb="md">Webhook Status</Title>

                <Stack gap="md">
                  <Group justify="space-between">
                    <Text size="sm">Webhook Status:</Text>
                    <Group gap="xs">
                      <Indicator color="green" size={8} />
                      <Text size="sm" c="green">Connected</Text>
                    </Group>
                  </Group>

                  <Text size="xs" c="dimmed">
                    Receiving real-time notifications at: https://myapp.com/webhooks/ekko
                  </Text>

                  <Divider />

                  <div>
                    <Text size="sm" fw={500} mb="xs">Recent Deliveries</Text>
                    <Stack gap="xs">
                      <Group justify="space-between">
                        <Text size="xs">alert.triggered</Text>
                        <Text size="xs" c="dimmed">2 min ago</Text>
                      </Group>
                      <Group justify="space-between">
                        <Text size="xs">transaction.detected</Text>
                        <Text size="xs" c="dimmed">5 min ago</Text>
                      </Group>
                      <Group justify="space-between">
                        <Text size="xs">alert.resolved</Text>
                        <Text size="xs" c="dimmed">12 min ago</Text>
                      </Group>
                    </Stack>
                  </div>

                  <Button variant="light" size="sm" fullWidth>
                    Configure
                  </Button>
                </Stack>
              </Card>

              <Card withBorder mt="md">
                <Title order={4} mb="md">Available Events</Title>

                <Stack gap="xs">
                  <Group justify="space-between">
                    <Text size="sm">alert.triggered</Text>
                    <Badge size="xs" variant="light">Active</Badge>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">alert.resolved</Text>
                    <Badge size="xs" variant="light">Active</Badge>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">transaction.detected</Text>
                    <Badge size="xs" variant="light">Active</Badge>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">wallet.balance_changed</Text>
                    <Badge size="xs" variant="light" color="gray">Inactive</Badge>
                  </Group>
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>

        <Tabs.Panel value="docs" pt="md">
          <Grid>
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <Card withBorder>
                <Title order={3} mb="md">API Documentation</Title>

                <Stack gap="lg">
                  <div>
                    <Title order={4} mb="md">Getting Started</Title>
                    <Text mb="md">
                      The Ekko API provides programmatic access to your wallet monitoring,
                      alert management, and transaction data. All API requests require authentication
                      using an API key.
                    </Text>

                    <Paper withBorder p="md" bg="gray.0">
                      <Text size="sm" fw={500} mb="xs">Base URL</Text>
                      <Code>https://api.ekko.com/v1</Code>
                    </Paper>
                  </div>

                  <div>
                    <Title order={4} mb="md">Authentication</Title>
                    <Text mb="md">
                      Include your API key in the Authorization header of every request:
                    </Text>

                    <Code block>
                      {`curl -H "Authorization: Bearer your-api-key" \\
     https://api.ekko.com/v1/wallets`}
                    </Code>
                  </div>

                  <div>
                    <Title order={4} mb="md">Endpoints</Title>
                    <Stack gap="md">
                      {endpoints.map((endpoint, index) => (
                        <Paper key={index} withBorder p="md">
                          <Group justify="space-between" mb="sm">
                            <Group gap="sm">
                              <Badge color={endpoint.method === 'GET' ? 'blue' : 'green'}>
                                {endpoint.method}
                              </Badge>
                              <Code>{endpoint.path}</Code>
                            </Group>
                            <Button
                              size="xs"
                              variant="light"
                              onClick={() => {
                                setSelectedEndpoint(`${endpoint.method} ${endpoint.path}`)
                                setActiveTab('tester')
                              }}
                            >
                              Try it
                            </Button>
                          </Group>

                          <Text size="sm" mb="md">{endpoint.description}</Text>

                          {endpoint.parameters && endpoint.parameters.length > 0 && (
                            <div>
                              <Text size="sm" fw={500} mb="xs">Parameters:</Text>
                              <Table>
                                <Table.Thead>
                                  <Table.Tr>
                                    <Table.Th>Name</Table.Th>
                                    <Table.Th>Type</Table.Th>
                                    <Table.Th>Required</Table.Th>
                                    <Table.Th>Description</Table.Th>
                                  </Table.Tr>
                                </Table.Thead>
                                <Table.Tbody>
                                  {endpoint.parameters.map((param, paramIndex) => (
                                    <Table.Tr key={paramIndex}>
                                      <Table.Td><Code>{param.name}</Code></Table.Td>
                                      <Table.Td>{param.type}</Table.Td>
                                      <Table.Td>
                                        <Badge
                                          size="xs"
                                          color={param.required ? 'red' : 'gray'}
                                          variant="light"
                                        >
                                          {param.required ? 'Required' : 'Optional'}
                                        </Badge>
                                      </Table.Td>
                                      <Table.Td>{param.description}</Table.Td>
                                    </Table.Tr>
                                  ))}
                                </Table.Tbody>
                              </Table>
                            </div>
                          )}

                          {endpoint.example_request && (
                            <div>
                              <Text size="sm" fw={500} mb="xs">Example Request:</Text>
                              <Code block>
                                {JSON.stringify(endpoint.example_request, null, 2)}
                              </Code>
                            </div>
                          )}
                        </Paper>
                      ))}
                    </Stack>
                  </div>

                  <div>
                    <Title order={4} mb="md">Rate Limits</Title>
                    <Text mb="md">
                      API requests are rate limited based on your API key configuration:
                    </Text>

                    <Table>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th>Access Level</Table.Th>
                          <Table.Th>Requests/Minute</Table.Th>
                          <Table.Th>Requests/Day</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        <Table.Tr>
                          <Table.Td>Read Only</Table.Td>
                          <Table.Td>100</Table.Td>
                          <Table.Td>10,000</Table.Td>
                        </Table.Tr>
                        <Table.Tr>
                          <Table.Td>Limited</Table.Td>
                          <Table.Td>500</Table.Td>
                          <Table.Td>50,000</Table.Td>
                        </Table.Tr>
                        <Table.Tr>
                          <Table.Td>Full Access</Table.Td>
                          <Table.Td>1,000</Table.Td>
                          <Table.Td>100,000</Table.Td>
                        </Table.Tr>
                      </Table.Tbody>
                    </Table>
                  </div>

                  <div>
                    <Title order={4} mb="md">Error Handling</Title>
                    <Text mb="md">
                      The API uses conventional HTTP response codes to indicate success or failure:
                    </Text>

                    <Stack gap="sm">
                      <Group>
                        <Badge color="green">200</Badge>
                        <Text size="sm">Success</Text>
                      </Group>
                      <Group>
                        <Badge color="yellow">400</Badge>
                        <Text size="sm">Bad Request - Invalid parameters</Text>
                      </Group>
                      <Group>
                        <Badge color="red">401</Badge>
                        <Text size="sm">Unauthorized - Invalid API key</Text>
                      </Group>
                      <Group>
                        <Badge color="red">429</Badge>
                        <Text size="sm">Rate Limited - Too many requests</Text>
                      </Group>
                      <Group>
                        <Badge color="red">500</Badge>
                        <Text size="sm">Server Error</Text>
                      </Group>
                    </Stack>
                  </div>
                </Stack>
              </Card>
            </Grid.Col>

            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Card withBorder>
                <Title order={4} mb="md">Quick Links</Title>

                <Stack gap="sm">
                  <Button
                    variant="light"
                    leftSection={<IconDownload size={16} />}
                    fullWidth
                  >
                    Download OpenAPI Spec
                  </Button>

                  <Button
                    variant="light"
                    leftSection={<IconCode size={16} />}
                    fullWidth
                    onClick={() => setActiveTab('tester')}
                  >
                    API Tester
                  </Button>

                  <Button
                    variant="light"
                    leftSection={<IconExternalLink size={16} />}
                    fullWidth
                    component="a"
                    href="#"
                    target="_blank"
                  >
                    Postman Collection
                  </Button>
                </Stack>
              </Card>

              <Card withBorder mt="md">
                <Title order={4} mb="md">SDKs & Libraries</Title>

                <Stack gap="sm">
                  <Group justify="space-between">
                    <Text size="sm">JavaScript/Node.js</Text>
                    <Button size="xs" variant="light">Install</Button>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">Python</Text>
                    <Button size="xs" variant="light">Install</Button>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">Go</Text>
                    <Button size="xs" variant="light">Install</Button>
                  </Group>
                  <Group justify="space-between">
                    <Text size="sm">PHP</Text>
                    <Button size="xs" variant="light">Install</Button>
                  </Group>
                </Stack>
              </Card>

              <Card withBorder mt="md">
                <Title order={4} mb="md">Support</Title>

                <Stack gap="sm">
                  <Text size="sm" c="dimmed">
                    Need help with the API? Check out our resources:
                  </Text>

                  <Button
                    variant="subtle"
                    leftSection={<IconExternalLink size={16} />}
                    fullWidth
                    component="a"
                    href="#"
                    target="_blank"
                  >
                    API Documentation
                  </Button>

                  <Button
                    variant="subtle"
                    leftSection={<IconExternalLink size={16} />}
                    fullWidth
                    component="a"
                    href="#"
                    target="_blank"
                  >
                    Community Forum
                  </Button>

                  <Button
                    variant="subtle"
                    leftSection={<IconExternalLink size={16} />}
                    fullWidth
                    component="a"
                    href="#"
                    target="_blank"
                  >
                    Contact Support
                  </Button>
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>
        </Tabs.Panel>
      </Tabs>

      {/* Create API Key Modal */}
      <CreateApiKeyModal
        opened={createKeyOpened}
        onClose={closeCreateKey}
        onSubmit={handleCreateApiKey}
      />

      {/* Create Webhook Modal */}
      <CreateWebhookModal
        opened={createWebhookOpened}
        onClose={closeCreateWebhook}
        onSubmit={async (data: any) => {
          await createWebhook(data)
          closeCreateWebhook()
        }}
      />
    </Container>
  )
}

// Create API Key Modal Component
function CreateApiKeyModal({ opened, onClose, onSubmit }: any) {
  const [formData, setFormData] = useState({
    name: '',
    access_level: 'read_only',
    expires_at: '',
    rate_limit_minute: 100,
    rate_limit_day: 10000
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
    setFormData({
      name: '',
      access_level: 'read_only',
      expires_at: '',
      rate_limit_minute: 100,
      rate_limit_day: 10000
    })
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Create API Key" size="md">
      <form onSubmit={handleSubmit}>
        <Stack gap="md">
          <TextInput
            label="Key Name"
            placeholder="e.g., Production Key"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />

          <Select
            label="Access Level"
            value={formData.access_level}
            onChange={(value) => setFormData({ ...formData, access_level: value || 'read_only' })}
            data={[
              { value: 'read_only', label: 'Read Only' },
              { value: 'limited', label: 'Limited Access' },
              { value: 'full', label: 'Full Access' }
            ]}
          />

          <TextInput
            label="Expires At (Optional)"
            type="date"
            value={formData.expires_at}
            onChange={(e) => setFormData({ ...formData, expires_at: e.target.value })}
          />

          <NumberInput
            label="Rate Limit (per minute)"
            value={formData.rate_limit_minute}
            onChange={(value) => setFormData({ ...formData, rate_limit_minute: Number(value) })}
            min={1}
            max={10000}
          />

          <NumberInput
            label="Rate Limit (per day)"
            value={formData.rate_limit_day}
            onChange={(value) => setFormData({ ...formData, rate_limit_day: Number(value) })}
            min={1}
            max={1000000}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Create API Key
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}

// Create Webhook Modal Component
function CreateWebhookModal({ opened, onClose, onSubmit }: any) {
  const [formData, setFormData] = useState<{
    name: string
    url: string
    events: string[]
    secret: string
  }>({
    name: '',
    url: '',
    events: [],
    secret: ''
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      ...formData,
      status: 'connected'
    })
    setFormData({
      name: '',
      url: '',
      events: [],
      secret: ''
    })
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Create Webhook" size="md">
      <form onSubmit={handleSubmit}>
        <Stack gap="md">
          <TextInput
            label="Webhook Name"
            placeholder="e.g., Alert Notifications"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            required
          />

          <TextInput
            label="Webhook URL"
            placeholder="https://your-app.com/webhooks/ekko"
            value={formData.url}
            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
            required
          />

          <MultiSelect
            label="Events"
            placeholder="Select events to subscribe to"
            value={formData.events}
            onChange={(value) => setFormData({ ...formData, events: value })}
            data={[
              { value: 'alert.triggered', label: 'Alert Triggered' },
              { value: 'alert.resolved', label: 'Alert Resolved' },
              { value: 'transaction.detected', label: 'Transaction Detected' },
              { value: 'wallet.balance_changed', label: 'Wallet Balance Changed' }
            ]}
          />

          <TextInput
            label="Secret (Optional)"
            placeholder="Webhook signing secret"
            value={formData.secret}
            onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
          />

          <Group justify="flex-end" mt="md">
            <Button variant="subtle" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Create Webhook
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
