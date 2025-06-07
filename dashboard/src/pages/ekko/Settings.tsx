import React, { useState, useEffect } from 'react';
import {
  Title,
  Text,
  Card,
  Group,
  Button,
  TextInput,
  Tabs,
  Switch,
  Stack,
  Select,
  Divider,
  PasswordInput,
  Textarea,
  NumberInput,
  ColorPicker,
  Box,
  ActionIcon,
  Badge,
  Paper,
  Tooltip,
  Alert,
} from '@mantine/core';
import {
  IconSettings,
  IconBell,
  IconUser,
  IconKey,
  IconServer,
  IconBrandGithub,
  IconDeviceDesktop,
  IconPalette,
  IconPlus,
  IconTrash,
  IconBrandSlack,
  IconBrandDiscord,
  IconBrandTelegram,
  IconMail,
  IconInfoCircle,
  IconCheck,
} from '@tabler/icons-react';
import { useForm } from '@mantine/form';

// Interface for notification channel
interface NotificationChannel {
  id: string;
  type: string;
  url: string;
  enabled: boolean;
}

// Validation functions for notification URLs
const validateNotificationUrl = (
  type: string,
  url: string
): { valid: boolean; message: string } => {
  if (!url) return { valid: false, message: 'URL cannot be empty' };

  switch (type) {
    case 'email':
      if (!url.startsWith('mailto://')) {
        return { valid: false, message: 'Email URL must start with mailto://' };
      }
      if (!url.includes('@')) {
        return { valid: false, message: 'Email URL must include an email address' };
      }
      return { valid: true, message: 'Valid email URL' };

    case 'slack':
      if (!url.startsWith('https://hooks.slack.com/') && !url.startsWith('slack://')) {
        return {
          valid: false,
          message: 'Slack URL must start with https://hooks.slack.com/ or slack://',
        };
      }
      return { valid: true, message: 'Valid Slack URL' };

    case 'discord':
      if (!url.startsWith('discord://') && !url.includes('discord.com/api/webhooks/')) {
        return {
          valid: false,
          message: 'Discord URL must be a valid webhook URL or start with discord://',
        };
      }
      return { valid: true, message: 'Valid Discord URL' };

    case 'telegram':
      if (!url.startsWith('tgram://') && !url.startsWith('telegram://')) {
        return { valid: false, message: 'Telegram URL must start with tgram:// or telegram://' };
      }
      return { valid: true, message: 'Valid Telegram URL' };

    default:
      return { valid: false, message: 'Unknown notification type' };
  }
};

// Helper function to get notification type icon
const getNotificationTypeIcon = (type: string) => {
  switch (type) {
    case 'email':
      return <IconMail size={16} />;
    case 'slack':
      return <IconBrandSlack size={16} />;
    case 'discord':
      return <IconBrandDiscord size={16} />;
    case 'telegram':
      return <IconBrandTelegram size={16} />;
    default:
      return <IconBell size={16} />;
  }
};

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [themeColor, setThemeColor] = useState('#228be6');
  const [hasChanges, setHasChanges] = useState(false);

  // General settings state
  const [apiEndpoint, setApiEndpoint] = useState('http://localhost:8000');
  const [refreshInterval, setRefreshInterval] = useState(30);
  const [timeFormat, setTimeFormat] = useState('24h');

  // Notification settings state
  const [notificationChannels, setNotificationChannels] = useState<NotificationChannel[]>([
    { id: '1', type: 'email', url: 'mailto://user:password@example.com', enabled: true },
    { id: '2', type: 'slack', url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ', enabled: false },
  ]);
  const [alertThreshold, setAlertThreshold] = useState('medium');
  const [newChannelType, setNewChannelType] = useState('email');
  const [newChannelUrl, setNewChannelUrl] = useState('');
  const [urlValidation, setUrlValidation] = useState<{ valid: boolean; message: string }>({
    valid: false,
    message: '',
  });

  // API settings state
  const [apiKey, setApiKey] = useState('••••••••••••••••••••••••••••••');

  // Node settings state
  const [defaultNetwork, setDefaultNetwork] = useState('avalanche');
  const [nodeTimeout, setNodeTimeout] = useState(10);
  const [maxRetries, setMaxRetries] = useState(3);

  // Account settings state
  const [username, setUsername] = useState('ekko_admin');
  const [email, setEmail] = useState('admin@ekko.chain');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Store original state for change detection
  const [originalState] = useState<{
    general: {
      apiEndpoint: string;
      refreshInterval: number;
      timeFormat: string;
    };
    notifications: {
      channels: string;
      alertThreshold: string;
    };
    api: {
      apiKey: string;
    };
    nodes: {
      defaultNetwork: string;
      nodeTimeout: number;
      maxRetries: number;
    };
    appearance: {
      themeColor: string;
    };
    account: {
      username: string;
      email: string;
      passwordChanged: boolean;
    };
  }>({
    general: {
      apiEndpoint: apiEndpoint,
      refreshInterval: refreshInterval,
      timeFormat: timeFormat,
    },
    notifications: {
      channels: JSON.stringify(notificationChannels),
      alertThreshold: alertThreshold,
    },
    api: {
      apiKey: apiKey,
    },
    nodes: {
      defaultNetwork: defaultNetwork,
      nodeTimeout: nodeTimeout,
      maxRetries: maxRetries,
    },
    appearance: {
      themeColor: themeColor,
    },
    account: {
      username: username,
      email: email,
      passwordChanged: false,
    },
  });

  // Check for changes whenever state changes
  useEffect(() => {
    const currentState = {
      general: {
        apiEndpoint: apiEndpoint,
        refreshInterval: refreshInterval,
        timeFormat: timeFormat,
      },
      notifications: {
        channels: JSON.stringify(notificationChannels),
        alertThreshold: alertThreshold,
      },
      api: {
        apiKey: apiKey,
      },
      nodes: {
        defaultNetwork: defaultNetwork,
        nodeTimeout: nodeTimeout,
        maxRetries: maxRetries,
      },
      appearance: {
        themeColor: themeColor,
      },
      account: {
        username: username,
        email: email,
        passwordChanged: currentPassword !== '' && newPassword !== '' && confirmPassword !== '',
      },
    };

    // Validate passwords if they're being changed
    if (currentPassword || newPassword || confirmPassword) {
      if (!currentPassword) {
        setPasswordError('Current password is required');
      } else if (!newPassword) {
        setPasswordError('New password is required');
      } else if (newPassword.length < 8) {
        setPasswordError('New password must be at least 8 characters');
      } else if (newPassword !== confirmPassword) {
        setPasswordError("New passwords don't match");
      } else {
        setPasswordError('');
      }
    } else {
      setPasswordError('');
    }

    // Compare original state with current state
    const hasStateChanged =
      JSON.stringify(originalState.general) !== JSON.stringify(currentState.general) ||
      originalState.notifications.channels !== currentState.notifications.channels ||
      originalState.notifications.alertThreshold !== currentState.notifications.alertThreshold ||
      originalState.api.apiKey !== currentState.api.apiKey ||
      JSON.stringify(originalState.nodes) !== JSON.stringify(currentState.nodes) ||
      originalState.appearance.themeColor !== currentState.appearance.themeColor ||
      originalState.account.username !== currentState.account.username ||
      originalState.account.email !== currentState.account.email ||
      currentState.account.passwordChanged;

    setHasChanges(hasStateChanged);
  }, [
    apiEndpoint,
    refreshInterval,
    timeFormat,
    notificationChannels,
    alertThreshold,
    apiKey,
    defaultNetwork,
    nodeTimeout,
    maxRetries,
    themeColor,
    username,
    email,
    currentPassword,
    newPassword,
    confirmPassword,
    originalState,
  ]);

  // Handle save changes
  const handleSaveChanges = () => {
    // Here you would typically make an API call to save the settings
    console.log('Saving settings...');

    // Validate password changes if on account tab
    if (activeTab === 'account' && currentPassword && newPassword) {
      if (passwordError) {
        alert(`Cannot save changes: ${passwordError}`);
        return;
      }
      console.log('Saving password changes...');
      // In a real implementation, you would make an API call to update the password
    }

    // Log the current state for debugging
    console.log('Current notification channels:', notificationChannels);

    // Save notification settings if on notifications tab
    if (activeTab === 'notifications') {
      // In a real implementation, you would make an API call to update notification settings
      console.log('Saving notification settings:', {
        channels: notificationChannels,
        alertThreshold: alertThreshold,
      });

      // Update the original state to reflect the current notification channels
      originalState.notifications.channels = JSON.stringify(notificationChannels);
      originalState.notifications.alertThreshold = alertThreshold;
    }

    // After successful save, update the original state to match current state
    // This would reset the hasChanges flag
    setHasChanges(false);
    alert('Settings saved successfully!');
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Settings</Title>
          <Text c="dimmed" size="sm">
            Configure your Ekko dashboard preferences
          </Text>
        </div>
        <Button variant="filled" disabled={!hasChanges} onClick={handleSaveChanges}>
          {hasChanges ? 'Save Changes' : 'No Changes'}
        </Button>
      </Group>

      <Card withBorder>
        <Tabs
          value={activeTab}
          onChange={(value: string | null) => setActiveTab(value || 'general')}
        >
          <Tabs.List mb="md">
            <Tabs.Tab value="general" leftSection={<IconSettings size={16} />}>
              General
            </Tabs.Tab>
            <Tabs.Tab value="notifications" leftSection={<IconBell size={16} />}>
              Notifications
            </Tabs.Tab>
            <Tabs.Tab value="api" leftSection={<IconKey size={16} />}>
              API Keys
            </Tabs.Tab>
            <Tabs.Tab value="nodes" leftSection={<IconServer size={16} />}>
              Node Settings
            </Tabs.Tab>
            {/* Appearance tab hidden for now */}
            {/* <Tabs.Tab value="appearance" leftSection={<IconPalette size={16} />}>
              Appearance
            </Tabs.Tab> */}
            <Tabs.Tab value="account" leftSection={<IconUser size={16} />}>
              Account
            </Tabs.Tab>
          </Tabs.List>

          {/* General Settings */}
          {activeTab === 'general' && (
            <Stack>
              <Title order={3} mb="sm">
                General Settings
              </Title>

              <TextInput
                label="API Endpoint"
                description="The base URL for the Ekko API"
                placeholder="http://localhost:8000"
                value={apiEndpoint}
                onChange={(e) => setApiEndpoint(e.currentTarget.value)}
              />

              <NumberInput
                label="Data Refresh Interval"
                description="How often to refresh data (in seconds)"
                placeholder="30"
                min={5}
                max={300}
                value={refreshInterval}
                onChange={(value: number | string) =>
                  setRefreshInterval(typeof value === 'number' ? value : 30)
                }
              />

              <Select
                label="Time Format"
                description="Choose how times are displayed"
                value={timeFormat}
                onChange={(value) => setTimeFormat(value || '24h')}
                data={[
                  { value: '12h', label: '12-hour (AM/PM)' },
                  { value: '24h', label: '24-hour' },
                ]}
              />

              <Switch
                label="Enable Debug Mode"
                description="Show additional debugging information"
                mt="md"
              />

              <Switch
                label="Use Mock Data"
                description="Use sample data instead of connecting to the API"
                mt="xs"
                defaultChecked
              />
            </Stack>
          )}

          {/* Notification Settings */}
          {activeTab === 'notifications' && (
            <Stack>
              <Title order={3} mb="sm">
                Notification Settings
              </Title>

              <Alert
                icon={<IconInfoCircle size={16} />}
                title="About Notification Channels"
                color="blue"
                mb="md"
              >
                Configure multiple notification channels to receive alerts. Each channel can be
                enabled or disabled individually. Use Apprise-compatible URLs for each service.
              </Alert>

              <Paper withBorder p="md" mb="md">
                <Title order={4} mb="sm">
                  Notification Channels
                </Title>

                {notificationChannels.length === 0 ? (
                  <Text c="dimmed" mb="md">
                    No notification channels configured. Add one below.
                  </Text>
                ) : (
                  <Stack mb="md">
                    {notificationChannels.map((channel) => (
                      <Group
                        key={channel.id}
                        justify="space-between"
                        p="xs"
                        style={{ border: '1px solid #eee', borderRadius: '4px' }}
                      >
                        <Group>
                          <Badge
                            leftSection={getNotificationTypeIcon(channel.type)}
                            color={channel.enabled ? 'green' : 'gray'}
                            variant="light"
                          >
                            {channel.type.charAt(0).toUpperCase() + channel.type.slice(1)}
                          </Badge>
                          <Text size="sm" style={{ wordBreak: 'break-all' }}>
                            {channel.url}
                          </Text>
                        </Group>
                        <Group gap="xs">
                          <Switch
                            checked={channel.enabled}
                            onChange={(event) => {
                              setNotificationChannels((channels) =>
                                channels.map((c) =>
                                  c.id === channel.id
                                    ? { ...c, enabled: event.currentTarget.checked }
                                    : c
                                )
                              );
                            }}
                            size="xs"
                          />
                          <ActionIcon
                            color="red"
                            variant="subtle"
                            onClick={() => {
                              setNotificationChannels((channels) =>
                                channels.filter((c) => c.id !== channel.id)
                              );
                            }}
                          >
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Group>
                      </Group>
                    ))}
                  </Stack>
                )}

                <Divider my="md" label="Add New Channel" labelPosition="center" />

                <Group align="flex-end" grow>
                  <Select
                    label="Channel Type"
                    value={newChannelType}
                    onChange={(value: string | null) => {
                      setNewChannelType(value || 'email');
                      setUrlValidation({ valid: false, message: '' });
                    }}
                    data={[
                      { value: 'email', label: 'Email' },
                      { value: 'slack', label: 'Slack' },
                      { value: 'discord', label: 'Discord' },
                      { value: 'telegram', label: 'Telegram' },
                    ]}
                  />
                  <TextInput
                    label="Channel URL"
                    placeholder={
                      newChannelType === 'email'
                        ? 'mailto://user:password@example.com'
                        : newChannelType === 'slack'
                          ? 'https://hooks.slack.com/services/...'
                          : newChannelType === 'discord'
                            ? 'discord://webhook_id/webhook_token'
                            : 'tgram://bot_token/chat_id'
                    }
                    value={newChannelUrl}
                    onChange={(e) => {
                      setNewChannelUrl(e.currentTarget.value);
                      setUrlValidation(
                        validateNotificationUrl(newChannelType, e.currentTarget.value)
                      );
                    }}
                    error={newChannelUrl && !urlValidation.valid ? urlValidation.message : null}
                    rightSection={
                      urlValidation.valid && (
                        <Tooltip label="Valid URL format">
                          <ActionIcon color="green" variant="subtle">
                            <IconCheck size={16} />
                          </ActionIcon>
                        </Tooltip>
                      )
                    }
                  />
                </Group>

                <Group justify="flex-end" mt="md">
                  <Button
                    leftSection={<IconPlus size={16} />}
                    onClick={() => {
                      if (urlValidation.valid) {
                        const newChannel: NotificationChannel = {
                          id: Date.now().toString(),
                          type: newChannelType,
                          url: newChannelUrl,
                          enabled: true,
                        };
                        setNotificationChannels([...notificationChannels, newChannel]);
                        setNewChannelUrl('');
                        setUrlValidation({ valid: false, message: '' });
                      }
                    }}
                    disabled={!urlValidation.valid}
                  >
                    Add Channel
                  </Button>
                </Group>

                <Box mt="md">
                  <Text size="sm" fw={500}>
                    URL Format Examples:
                  </Text>
                  <Text size="xs" c="dimmed">
                    Email: mailto://user:password@gmail.com/?to=target@example.com
                  </Text>
                  <Text size="xs" c="dimmed">
                    Slack: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX
                  </Text>
                  <Text size="xs" c="dimmed">
                    Discord: discord://webhook_id/webhook_token
                  </Text>
                  <Text size="xs" c="dimmed">
                    Telegram: tgram://bot_token/chat_id
                  </Text>
                </Box>
              </Paper>

              <Divider my="md" />

              <Select
                label="Alert Threshold"
                description="Minimum alert level to notify"
                value={alertThreshold}
                onChange={(value) => setAlertThreshold(value || 'medium')}
                data={[
                  { value: 'low', label: 'Low (All Alerts)' },
                  { value: 'medium', label: 'Medium (Medium & High)' },
                  { value: 'high', label: 'High (Critical Alerts Only)' },
                ]}
              />

              <Switch
                label="Browser Notifications"
                description="Show desktop notifications in your browser"
                mt="md"
                defaultChecked
              />
            </Stack>
          )}

          {/* API Settings */}
          {activeTab === 'api' && (
            <Stack>
              <Title order={3} mb="sm">
                API Keys
              </Title>

              <PasswordInput
                label="Current API Key"
                description="Your Ekko API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.currentTarget.value)}
                mb="md"
              />

              <Group>
                <Button variant="outline">Generate New Key</Button>
                <Button variant="light">Copy Key</Button>
              </Group>

              <Divider my="md" label="External APIs" labelPosition="center" />

              <TextInput
                label="Infura API Key"
                description="API key for Infura services"
                placeholder="Enter your Infura API key"
              />

              <TextInput
                label="Etherscan API Key"
                description="API key for Etherscan"
                placeholder="Enter your Etherscan API key"
                mt="md"
              />

              <TextInput
                label="Snowtrace API Key"
                description="API key for Snowtrace"
                placeholder="Enter your Snowtrace API key"
                mt="md"
              />
            </Stack>
          )}

          {/* Node Settings */}
          {activeTab === 'nodes' && (
            <Stack>
              <Title order={3} mb="sm">
                Node Settings
              </Title>

              <Select
                label="Default Network"
                description="Primary blockchain network"
                value={defaultNetwork}
                onChange={(value) => setDefaultNetwork(value || 'avalanche')}
                data={[
                  { value: 'avalanche', label: 'Avalanche' },
                  { value: 'ethereum', label: 'Ethereum' },
                  { value: 'bitcoin', label: 'Bitcoin' },
                  { value: 'polygon', label: 'Polygon' },
                ]}
              />

              <NumberInput
                label="Node Request Timeout"
                description="Seconds to wait for node responses"
                placeholder="10"
                min={1}
                max={60}
                value={nodeTimeout}
                onChange={(value: number | string) =>
                  setNodeTimeout(typeof value === 'number' ? value : 10)
                }
                mt="md"
              />

              <NumberInput
                label="Max Retries"
                description="Number of times to retry failed requests"
                placeholder="3"
                min={0}
                max={10}
                value={maxRetries}
                onChange={(value: number | string) =>
                  setMaxRetries(typeof value === 'number' ? value : 3)
                }
                mt="md"
              />

              <Switch
                label="Auto-switch Nodes"
                description="Automatically switch to backup nodes on failure"
                mt="md"
                defaultChecked
              />

              <Switch
                label="Node Health Monitoring"
                description="Continuously monitor node health"
                mt="md"
                defaultChecked
              />
            </Stack>
          )}

          {/* Appearance Settings */}
          {activeTab === 'appearance' && (
            <Stack>
              <Title order={3} mb="sm">
                Appearance Settings
              </Title>

              <Text fw={500} mb="xs">
                Theme Color
              </Text>
              <ColorPicker
                format="hex"
                value={themeColor}
                onChange={setThemeColor}
                swatches={[
                  '#25262b',
                  '#868e96',
                  '#fa5252',
                  '#e64980',
                  '#be4bdb',
                  '#7950f2',
                  '#4c6ef5',
                  '#228be6',
                  '#15aabf',
                  '#12b886',
                  '#40c057',
                  '#82c91e',
                  '#fab005',
                  '#fd7e14',
                ]}
              />

              <Divider my="md" />

              <Select
                label="Layout Type"
                description="Dashboard layout style"
                defaultValue="sidebar"
                data={[
                  { value: 'sidebar', label: 'Simple Sidebar' },
                  { value: 'decked', label: 'Decked Sidebar' },
                  { value: 'collapsed', label: 'Collapsed Sidebar' },
                ]}
                mt="md"
              />

              <Select
                label="Theme Mode"
                description="Light or dark appearance"
                defaultValue="light"
                data={[
                  { value: 'light', label: 'Light Mode' },
                  { value: 'dark', label: 'Dark Mode' },
                  { value: 'system', label: 'System Default' },
                ]}
                mt="md"
              />

              <Switch
                label="Compact Mode"
                description="Use more compact spacing throughout the UI"
                mt="md"
              />
            </Stack>
          )}

          {/* Account Settings */}
          {activeTab === 'account' && (
            <Stack>
              <Title order={3} mb="sm">
                Account Settings
              </Title>

              <TextInput
                label="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                mb="md"
              />

              <TextInput
                label="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                mb="md"
              />

              <PasswordInput
                label="Current Password"
                placeholder="Enter current password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                mb="md"
              />

              <PasswordInput
                label="New Password"
                placeholder="Enter new password"
                description="Must be at least 8 characters"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                mb="md"
              />

              <PasswordInput
                label="Confirm New Password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                error={passwordError}
                mb="md"
              />

              <Divider my="md" />

              {passwordError && (
                <Alert color="red" mb="md" title="Password Error">
                  {passwordError}
                </Alert>
              )}

              <Group>
                <Button
                  color="blue"
                  variant="filled"
                  disabled={!hasChanges || !!passwordError}
                  onClick={handleSaveChanges}
                >
                  Save Account Changes
                </Button>
                <Button color="red" variant="outline">
                  Log Out
                </Button>
              </Group>
            </Stack>
          )}
        </Tabs>
      </Card>
    </div>
  );
}
