import { useState, useEffect } from 'react'
import {
  Container,
  Title,
  Text,
  Tabs,
  Stack,
  Button,
  Group,
  Alert,
  Loader,
  Center,
  Modal,
  TextInput,
  Select,
  Textarea,
} from '@mantine/core'
import {
  IconBell,
  IconBrandSlack,
  IconBrandTelegram,
  IconBrandDiscord,
  IconWebhook,
  IconMail,
  IconDeviceMobile,
  IconPlus,
  IconAlertCircle,
  IconCheck,
  IconKey,
  IconLink,
  IconNetwork,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { SlackChannelCard } from '../../components/notifications/SlackChannelCard'
import { TelegramChannelCard } from '../../components/notifications/TelegramChannelCard'
import { WebhookChannelCard } from '../../components/notifications/WebhookChannelCard'
import { DefaultNetworkAlertCard } from '../../components/alerts/DefaultNetworkAlertCard'
import notificationsApiService, {
  type NotificationChannelEndpoint,
  type CreateSlackChannelRequest,
  type CreateTelegramChannelRequest,
  type DeliveryStatsResponse,
} from '../../services/notifications-api'
import groupsApiService, { type DefaultNetworkAlert } from '../../services/groups-api'

export function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<string | null>('slack')
  const [channels, setChannels] = useState<NotificationChannelEndpoint[]>([])
  const [channelStats, setChannelStats] = useState<Map<string, DeliveryStatsResponse>>(new Map())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isAddTelegramModalOpen, setIsAddTelegramModalOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Form state for new Slack channel
  const [newSlackChannel, setNewSlackChannel] = useState<CreateSlackChannelRequest>({
    label: '',
    webhook_url: '',
    channel: '#alerts',
    workspace_name: 'Ekko Workspace',
  })

  // Form state for new Telegram channel
  const [newTelegramChannel, setNewTelegramChannel] = useState<CreateTelegramChannelRequest>({
    label: '',
    bot_token: '',
    chat_id: '',
    username: '',
  })

  // Webhook channel modal state
  const [isAddWebhookModalOpen, setIsAddWebhookModalOpen] = useState(false)
  const [newWebhookChannel, setNewWebhookChannel] = useState({
    label: '',
    url: '',
    secret: '',
    headers: '',
    method: 'POST' as 'POST' | 'GET',
  })

  // Default network alerts state
  const [defaultAlerts, setDefaultAlerts] = useState<DefaultNetworkAlert[]>([])
  const [isLoadingDefaultAlerts, setIsLoadingDefaultAlerts] = useState(false)



  // Load channels
  const loadChannels = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await notificationsApiService.getChannels({
        channel_type: activeTab as any,
      })

      setChannels(response.results)

      // Load stats for each channel
      const statsPromises = response.results.map(async (channel) => {
        try {
          const stats = await notificationsApiService.getChannelStats(channel.id)
          return { channelId: channel.id, stats }
        } catch (err) {
          // Stats endpoint might not exist yet, fail gracefully
          return null
        }
      })

      const statsResults = await Promise.all(statsPromises)
      const newStatsMap = new Map<string, DeliveryStatsResponse>()
      statsResults.forEach((result) => {
        if (result) {
          newStatsMap.set(result.channelId, result.stats)
        }
      })
      setChannelStats(newStatsMap)
    } catch (err: any) {
      setError(err.message || 'Failed to load notification channels')
      console.error('Load channels error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'defaults') {
      loadDefaultAlerts()
    } else {
      loadChannels()
    }
  }, [activeTab])

  // Handle toggle channel
  const handleToggleChannel = async (channelId: string, enabled: boolean) => {
    try {
      await notificationsApiService.toggleChannel(channelId, enabled)
      notifications.show({
        title: 'Success',
        message: `Channel ${enabled ? 'enabled' : 'disabled'} successfully`,
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to toggle channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  // Handle delete channel
  const handleDeleteChannel = async (channelId: string) => {
    try {
      await notificationsApiService.deleteChannel(channelId)
      notifications.show({
        title: 'Success',
        message: 'Channel deleted successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to delete channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  // Handle test channel
  const handleTestChannel = async (channelId: string) => {
    try {
      const result = await notificationsApiService.testChannel(
        channelId,
        'Test message from Ekko Dashboard'
      )
      notifications.show({
        title: 'Test Successful',
        message: result.message || 'Test message sent successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err: any) {
      notifications.show({
        title: 'Test Failed',
        message: err.message || 'Failed to send test message',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  // Handle create Slack channel
  const handleCreateSlackChannel = async () => {
    if (!newSlackChannel.label || !newSlackChannel.webhook_url) {
      notifications.show({
        title: 'Validation Error',
        message: 'Label and webhook URL are required',
        color: 'yellow',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    setIsSubmitting(true)
    try {
      await notificationsApiService.createSlackChannel(newSlackChannel)
      notifications.show({
        title: 'Success',
        message: 'Slack channel created successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      setIsAddModalOpen(false)
      setNewSlackChannel({
        label: '',
        webhook_url: '',
        channel: '#alerts',
        workspace_name: 'Ekko Workspace',
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to create Slack channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle create Telegram channel
  const handleCreateTelegramChannel = async () => {
    if (!newTelegramChannel.label || !newTelegramChannel.bot_token || !newTelegramChannel.chat_id) {
      notifications.show({
        title: 'Validation Error',
        message: 'Label, bot token, and chat ID are required',
        color: 'yellow',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    setIsSubmitting(true)
    try {
      await notificationsApiService.createTelegramChannel(newTelegramChannel)
      notifications.show({
        title: 'Success',
        message: 'Telegram channel created successfully. Please verify by sending /subscribe to the bot.',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      setIsAddTelegramModalOpen(false)
      setNewTelegramChannel({
        label: '',
        bot_token: '',
        chat_id: '',
        username: '',
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to create Telegram channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle verify Telegram channel
  const handleVerifyChannel = async (channelId: string, code: string) => {
    try {
      await notificationsApiService.verifyChannel(channelId, code)
      notifications.show({
        title: 'Verification Successful',
        message: 'Telegram channel verified successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Verification Failed',
        message: err.message || 'Failed to verify channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  // Load default network alerts
  const loadDefaultAlerts = async () => {
    setIsLoadingDefaultAlerts(true)
    try {
      const response = await groupsApiService.getDefaultNetworkAlerts()
      setDefaultAlerts(response.results)
    } catch (err: any) {
      console.error('Failed to load default network alerts:', err)
    } finally {
      setIsLoadingDefaultAlerts(false)
    }
  }

  // Handle toggle default network alert
  const handleToggleDefaultAlert = async (alertId: string, enabled: boolean) => {
    try {
      await groupsApiService.toggleDefaultNetworkAlert(alertId, enabled)
      notifications.show({
        title: 'Success',
        message: `Default alert ${enabled ? 'enabled' : 'disabled'} successfully`,
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      await loadDefaultAlerts()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to toggle default alert',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    }
  }

  // Handle create Webhook channel
  const handleCreateWebhookChannel = async () => {
    if (!newWebhookChannel.label || !newWebhookChannel.url) {
      notifications.show({
        title: 'Validation Error',
        message: 'Label and webhook URL are required',
        color: 'yellow',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    // Validate URL format
    try {
      new URL(newWebhookChannel.url)
    } catch {
      notifications.show({
        title: 'Validation Error',
        message: 'Please enter a valid URL',
        color: 'yellow',
        icon: <IconAlertCircle size={16} />,
      })
      return
    }

    // Parse headers if provided
    let parsedHeaders: Record<string, string> = {}
    if (newWebhookChannel.headers.trim()) {
      try {
        parsedHeaders = JSON.parse(newWebhookChannel.headers)
      } catch {
        notifications.show({
          title: 'Validation Error',
          message: 'Headers must be valid JSON (e.g., {"Authorization": "Bearer token"})',
          color: 'yellow',
          icon: <IconAlertCircle size={16} />,
        })
        return
      }
    }

    setIsSubmitting(true)
    try {
      await notificationsApiService.createWebhookChannel({
        label: newWebhookChannel.label,
        url: newWebhookChannel.url,
        method: newWebhookChannel.method,
        headers: parsedHeaders,
        secret: newWebhookChannel.secret || undefined,
      })
      notifications.show({
        title: 'Success',
        message: 'Webhook channel created successfully',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      setIsAddWebhookModalOpen(false)
      setNewWebhookChannel({
        label: '',
        url: '',
        secret: '',
        headers: '',
        method: 'POST',
      })
      await loadChannels()
    } catch (err: any) {
      notifications.show({
        title: 'Error',
        message: err.message || 'Failed to create webhook channel',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderSlackTab = () => {
    if (isLoading) {
      return (
        <Center h={300}>
          <Loader size="lg" />
        </Center>
      )
    }

    if (error) {
      return (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )
    }

    const slackChannels = channels.filter((ch) => ch.channel_type === 'slack')

    return (
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text size="sm" c="dimmed">
              Configure Slack webhook integrations to receive real-time alerts in your workspace.
            </Text>
          </div>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setIsAddModalOpen(true)}
          >
            Add Slack Channel
          </Button>
        </Group>

        {slackChannels.length === 0 ? (
          <Alert icon={<IconBrandSlack size={16} />} title="No Slack channels" color="blue">
            You haven't configured any Slack channels yet. Click "Add Slack Channel" to get started.
          </Alert>
        ) : (
          <Stack gap="md">
            {slackChannels.map((channel) => (
              <SlackChannelCard
                key={channel.id}
                channel={channel}
                onToggle={handleToggleChannel}
                onDelete={handleDeleteChannel}
                onTest={handleTestChannel}
                stats={channelStats.get(channel.id)}
              />
            ))}
          </Stack>
        )}
      </Stack>
    )
  }

  const renderTelegramTab = () => {
    if (isLoading) {
      return (
        <Center h={300}>
          <Loader size="lg" />
        </Center>
      )
    }

    if (error) {
      return (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )
    }

    const telegramChannels = channels.filter((ch) => ch.channel_type === 'telegram')

    return (
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text size="sm" c="dimmed">
              Configure Telegram bot integrations to receive real-time alerts via Telegram.
            </Text>
          </div>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setIsAddTelegramModalOpen(true)}
          >
            Add Telegram Channel
          </Button>
        </Group>

        {telegramChannels.length === 0 ? (
          <Alert icon={<IconBrandTelegram size={16} />} title="No Telegram channels" color="blue">
            You haven't configured any Telegram channels yet. Click "Add Telegram Channel" to get started.
          </Alert>
        ) : (
          <Stack gap="md">
            {telegramChannels.map((channel) => (
              <TelegramChannelCard
                key={channel.id}
                channel={channel}
                onToggle={handleToggleChannel}
                onDelete={handleDeleteChannel}
                onTest={handleTestChannel}
                onVerify={handleVerifyChannel}
                stats={channelStats.get(channel.id)}
              />
            ))}
          </Stack>
        )}
      </Stack>
    )
  }

  const renderWebhookTab = () => {
    if (isLoading) {
      return (
        <Center h={300}>
          <Loader size="lg" />
        </Center>
      )
    }

    if (error) {
      return (
        <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
          {error}
        </Alert>
      )
    }

    const webhookChannels = channels.filter((ch) => ch.channel_type === 'webhook')

    return (
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text size="sm" c="dimmed">
              Configure webhook endpoints to receive real-time alerts via HTTP requests with health monitoring.
            </Text>
          </div>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => setIsAddWebhookModalOpen(true)}
          >
            Add Webhook
          </Button>
        </Group>

        {webhookChannels.length === 0 ? (
          <Alert icon={<IconWebhook size={16} />} title="No webhook channels" color="blue">
            You haven't configured any webhook channels yet. Click "Add Webhook" to get started.
          </Alert>
        ) : (
          <Stack gap="md">
            {webhookChannels.map((channel) => (
              <WebhookChannelCard
                key={channel.id}
                channel={channel}
                onToggle={handleToggleChannel}
                onDelete={handleDeleteChannel}
                onTest={handleTestChannel}
                stats={channelStats.get(channel.id)}
              />
            ))}
          </Stack>
        )}
      </Stack>
    )
  }

  const renderDefaultAlertsTab = () => {
    if (isLoadingDefaultAlerts) {
      return (
        <Center h={300}>
          <Loader size="lg" />
        </Center>
      )
    }

    return (
      <Stack gap="md">
        <div>
          <Text size="sm" c="dimmed">
            Default network alerts are system-wide fallback alerts that apply to all your wallets
            on each blockchain network. Toggle these to enable or disable default monitoring.
          </Text>
        </div>

        {defaultAlerts.length === 0 ? (
          <Alert icon={<IconNetwork size={16} />} title="No default alerts configured" color="blue">
            No default network alerts are available yet. These will be configured by the system administrator.
          </Alert>
        ) : (
          <Stack gap="md">
            {defaultAlerts.map((alert) => (
              <DefaultNetworkAlertCard
                key={alert.id}
                alert={alert}
                onToggle={handleToggleDefaultAlert}
              />
            ))}
          </Stack>
        )}
      </Stack>
    )
  }

  const renderPlaceholderTab = (type: string) => (
    <Alert icon={<IconAlertCircle size={16} />} title="Coming Soon" color="blue">
      {type} notifications will be available soon.
    </Alert>
  )

  return (
    <Container size="lg" py="xl">
      <Stack gap="lg">
        {/* Header */}
        <div>
          <Group gap="sm" mb="xs">
            <IconBell size={28} />
            <Title order={2}>Notification Channels</Title>
          </Group>
          <Text size="sm" c="dimmed">
            Manage how you receive alerts from Ekko. Configure multiple channels and customize
            delivery preferences.
          </Text>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="slack" leftSection={<IconBrandSlack size={16} />}>
              Slack
            </Tabs.Tab>
            <Tabs.Tab value="telegram" leftSection={<IconBrandTelegram size={16} />}>
              Telegram
            </Tabs.Tab>
            <Tabs.Tab value="discord" leftSection={<IconBrandDiscord size={16} />}>
              Discord
            </Tabs.Tab>
            <Tabs.Tab value="webhook" leftSection={<IconWebhook size={16} />}>
              Webhooks
            </Tabs.Tab>
            <Tabs.Tab value="email" leftSection={<IconMail size={16} />}>
              Email
            </Tabs.Tab>
            <Tabs.Tab value="sms" leftSection={<IconDeviceMobile size={16} />}>
              SMS
            </Tabs.Tab>
            <Tabs.Tab value="defaults" leftSection={<IconNetwork size={16} />}>
              Default Alerts
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="slack" pt="md">
            {renderSlackTab()}
          </Tabs.Panel>

          <Tabs.Panel value="telegram" pt="md">
            {renderTelegramTab()}
          </Tabs.Panel>

          <Tabs.Panel value="discord" pt="md">
            {renderPlaceholderTab('Discord')}
          </Tabs.Panel>

          <Tabs.Panel value="webhook" pt="md">
            {renderWebhookTab()}
          </Tabs.Panel>

          <Tabs.Panel value="email" pt="md">
            {renderPlaceholderTab('Email')}
          </Tabs.Panel>

          <Tabs.Panel value="sms" pt="md">
            {renderPlaceholderTab('SMS')}
          </Tabs.Panel>

          <Tabs.Panel value="defaults" pt="md">
            {renderDefaultAlertsTab()}
          </Tabs.Panel>
        </Tabs>

        {/* Add Slack Channel Modal */}
        <Modal
          opened={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          title="Add Slack Channel"
          size="lg"
        >
          <Stack gap="md">
            <TextInput
              label="Channel Label"
              placeholder="e.g., Team Alerts, Critical Notifications"
              description="A friendly name to identify this Slack channel"
              required
              value={newSlackChannel.label}
              onChange={(e) =>
                setNewSlackChannel({ ...newSlackChannel, label: e.target.value })
              }
            />

            <TextInput
              label="Webhook URL"
              placeholder="https://hooks.slack.com/services/..."
              description="Get this from your Slack workspace's Incoming Webhooks settings"
              required
              value={newSlackChannel.webhook_url}
              onChange={(e) =>
                setNewSlackChannel({ ...newSlackChannel, webhook_url: e.target.value })
              }
            />

            <TextInput
              label="Channel Name"
              placeholder="#alerts"
              description="The Slack channel where alerts will be posted"
              value={newSlackChannel.channel}
              onChange={(e) =>
                setNewSlackChannel({ ...newSlackChannel, channel: e.target.value })
              }
            />

            <TextInput
              label="Workspace Name"
              placeholder="Ekko Workspace"
              description="Optional: name of your Slack workspace"
              value={newSlackChannel.workspace_name}
              onChange={(e) =>
                setNewSlackChannel({ ...newSlackChannel, workspace_name: e.target.value })
              }
            />

            <Group justify="flex-end" mt="md">
              <Button variant="subtle" onClick={() => setIsAddModalOpen(false)}>
                Cancel
              </Button>
              <Button
                loading={isSubmitting}
                onClick={handleCreateSlackChannel}
                leftSection={<IconBrandSlack size={16} />}
              >
                Add Channel
              </Button>
            </Group>
          </Stack>
        </Modal>

        {/* Add Telegram Channel Modal */}
        <Modal
          opened={isAddTelegramModalOpen}
          onClose={() => setIsAddTelegramModalOpen(false)}
          title="Add Telegram Channel"
          size="lg"
        >
          <Stack gap="md">
            <TextInput
              label="Channel Label"
              placeholder="e.g., Team Alerts, Critical Notifications"
              description="A friendly name to identify this Telegram channel"
              required
              value={newTelegramChannel.label}
              onChange={(e) =>
                setNewTelegramChannel({ ...newTelegramChannel, label: e.target.value })
              }
            />

            <TextInput
              label="Bot Token"
              placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
              description="Get this from @BotFather on Telegram"
              required
              value={newTelegramChannel.bot_token}
              onChange={(e) =>
                setNewTelegramChannel({ ...newTelegramChannel, bot_token: e.target.value })
              }
            />

            <TextInput
              label="Chat ID"
              placeholder="-1001234567890"
              description="The Telegram chat ID where alerts will be sent"
              required
              value={newTelegramChannel.chat_id}
              onChange={(e) =>
                setNewTelegramChannel({ ...newTelegramChannel, chat_id: e.target.value })
              }
            />

            <TextInput
              label="Username"
              placeholder="@ekko_alerts_bot"
              description="Optional: bot username for display"
              value={newTelegramChannel.username}
              onChange={(e) =>
                setNewTelegramChannel({ ...newTelegramChannel, username: e.target.value })
              }
            />

            <Alert icon={<IconAlertCircle size={16} />} title="Verification Required" color="blue">
              <Text size="xs">
                After creating the channel, you'll need to verify it by sending{' '}
                <code>/subscribe</code> to your bot and entering the verification code.
              </Text>
            </Alert>

            <Group justify="flex-end" mt="md">
              <Button variant="subtle" onClick={() => setIsAddTelegramModalOpen(false)}>
                Cancel
              </Button>
              <Button
                loading={isSubmitting}
                onClick={handleCreateTelegramChannel}
                leftSection={<IconBrandTelegram size={16} />}
              >
                Add Channel
              </Button>
            </Group>
          </Stack>
        </Modal>

        {/* Add Webhook Channel Modal */}
        <Modal
          opened={isAddWebhookModalOpen}
          onClose={() => setIsAddWebhookModalOpen(false)}
          title="Add Webhook Channel"
          size="lg"
        >
          <Stack gap="md">
            <TextInput
              label="Channel Label"
              placeholder="e.g., My Backend API, Alert Processor"
              description="A friendly name to identify this webhook"
              required
              leftSection={<IconWebhook size={16} />}
              value={newWebhookChannel.label}
              onChange={(e) =>
                setNewWebhookChannel({ ...newWebhookChannel, label: e.target.value })
              }
            />

            <TextInput
              label="Webhook URL"
              placeholder="https://api.example.com/webhooks/alerts"
              description="The endpoint that will receive alert notifications"
              required
              leftSection={<IconLink size={16} />}
              value={newWebhookChannel.url}
              onChange={(e) =>
                setNewWebhookChannel({ ...newWebhookChannel, url: e.target.value })
              }
            />

            <Select
              label="HTTP Method"
              description="The HTTP method to use when sending alerts"
              data={[
                { value: 'POST', label: 'POST (recommended)' },
                { value: 'GET', label: 'GET' },
              ]}
              value={newWebhookChannel.method}
              onChange={(value) =>
                setNewWebhookChannel({
                  ...newWebhookChannel,
                  method: (value as 'POST' | 'GET') || 'POST',
                })
              }
            />

            <TextInput
              label="Secret Key"
              placeholder="your-webhook-secret"
              description="Optional: Used to sign requests with HMAC-SHA256 for verification"
              leftSection={<IconKey size={16} />}
              value={newWebhookChannel.secret}
              onChange={(e) =>
                setNewWebhookChannel({ ...newWebhookChannel, secret: e.target.value })
              }
            />

            <Textarea
              label="Custom Headers"
              placeholder='{"Authorization": "Bearer your-token", "X-Custom-Header": "value"}'
              description="Optional: JSON object of headers to include in requests"
              minRows={3}
              value={newWebhookChannel.headers}
              onChange={(e) =>
                setNewWebhookChannel({ ...newWebhookChannel, headers: e.target.value })
              }
            />

            <Alert icon={<IconAlertCircle size={16} />} title="Webhook Payload Format" color="blue">
              <Text size="xs">
                Alerts are sent as JSON with fields: <code>alert_id</code>, <code>type</code>,{' '}
                <code>message</code>, <code>data</code>, <code>timestamp</code>. If a secret is
                provided, requests include an <code>X-Ekko-Signature</code> header for HMAC verification.
              </Text>
            </Alert>

            <Group justify="flex-end" mt="md">
              <Button variant="subtle" onClick={() => setIsAddWebhookModalOpen(false)}>
                Cancel
              </Button>
              <Button
                loading={isSubmitting}
                onClick={handleCreateWebhookChannel}
                leftSection={<IconWebhook size={16} />}
              >
                Add Webhook
              </Button>
            </Group>
          </Stack>
        </Modal>
      </Stack>
    </Container>
  )
}
