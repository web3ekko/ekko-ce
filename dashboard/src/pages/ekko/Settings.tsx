import React, { useState } from 'react';
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
  Box
} from '@mantine/core';
import { 
  IconSettings, 
  IconBell, 
  IconUser, 
  IconKey,
  IconServer,
  IconBrandGithub,
  IconDeviceDesktop,
  IconPalette
} from '@tabler/icons-react';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [themeColor, setThemeColor] = useState('#228be6');
  
  // General settings state
  const [apiEndpoint, setApiEndpoint] = useState('http://localhost:8000');
  const [refreshInterval, setRefreshInterval] = useState(30);
  const [timeFormat, setTimeFormat] = useState('24h');
  
  // Notification settings state
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [slackNotifications, setSlackNotifications] = useState(false);
  const [slackWebhook, setSlackWebhook] = useState('');
  const [alertThreshold, setAlertThreshold] = useState('medium');
  
  // API settings state
  const [apiKey, setApiKey] = useState('••••••••••••••••••••••••••••••');
  
  // Node settings state
  const [defaultNetwork, setDefaultNetwork] = useState('avalanche');
  const [nodeTimeout, setNodeTimeout] = useState(10);
  const [maxRetries, setMaxRetries] = useState(3);

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Settings</Title>
          <Text c="dimmed" size="sm">Configure your Ekko dashboard preferences</Text>
        </div>
        <Button variant="filled">Save Changes</Button>
      </Group>
      
      <Card withBorder>
        <Tabs value={activeTab} onChange={setActiveTab}>
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
            <Tabs.Tab value="appearance" leftSection={<IconPalette size={16} />}>
              Appearance
            </Tabs.Tab>
            <Tabs.Tab value="account" leftSection={<IconUser size={16} />}>
              Account
            </Tabs.Tab>
          </Tabs.List>
          
          {/* General Settings */}
          {activeTab === 'general' && (
            <Stack>
              <Title order={3} mb="sm">General Settings</Title>
              
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
                onChange={(value) => setRefreshInterval(value || 30)}
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
              <Title order={3} mb="sm">Notification Settings</Title>
              
              <Switch
                label="Email Notifications"
                description="Receive alerts via email"
                checked={emailNotifications}
                onChange={(event) => setEmailNotifications(event.currentTarget.checked)}
                mt="md"
              />
              
              <Divider my="md" />
              
              <Switch
                label="Slack Notifications"
                description="Receive alerts via Slack"
                checked={slackNotifications}
                onChange={(event) => setSlackNotifications(event.currentTarget.checked)}
                mt="md"
              />
              
              {slackNotifications && (
                <TextInput
                  label="Slack Webhook URL"
                  description="The webhook URL for your Slack channel"
                  placeholder="https://hooks.slack.com/services/..."
                  value={slackWebhook}
                  onChange={(e) => setSlackWebhook(e.currentTarget.value)}
                  mt="xs"
                />
              )}
              
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
              <Title order={3} mb="sm">API Keys</Title>
              
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
              <Title order={3} mb="sm">Node Settings</Title>
              
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
                onChange={(value) => setNodeTimeout(value || 10)}
                mt="md"
              />
              
              <NumberInput
                label="Max Retries"
                description="Number of times to retry failed requests"
                placeholder="3"
                min={0}
                max={10}
                value={maxRetries}
                onChange={(value) => setMaxRetries(value || 3)}
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
              <Title order={3} mb="sm">Appearance Settings</Title>
              
              <Text fw={500} mb="xs">Theme Color</Text>
              <ColorPicker
                format="hex"
                value={themeColor}
                onChange={setThemeColor}
                swatches={[
                  '#25262b', '#868e96', '#fa5252', '#e64980', '#be4bdb', '#7950f2',
                  '#4c6ef5', '#228be6', '#15aabf', '#12b886', '#40c057', '#82c91e',
                  '#fab005', '#fd7e14',
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
              <Title order={3} mb="sm">Account Settings</Title>
              
              <TextInput
                label="Username"
                defaultValue="ekko_admin"
                mb="md"
              />
              
              <TextInput
                label="Email"
                defaultValue="admin@ekko.chain"
                mb="md"
              />
              
              <PasswordInput
                label="Current Password"
                placeholder="Enter current password"
                mb="md"
              />
              
              <PasswordInput
                label="New Password"
                placeholder="Enter new password"
                mb="md"
              />
              
              <PasswordInput
                label="Confirm New Password"
                placeholder="Confirm new password"
                mb="md"
              />
              
              <Divider my="md" />
              
              <Button color="red" variant="outline">Log Out</Button>
            </Stack>
          )}
        </Tabs>
      </Card>
    </div>
  );
}
