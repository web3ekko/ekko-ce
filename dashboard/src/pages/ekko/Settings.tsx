import React, { useState, useEffect } from 'react';
import {
  Text,
  Group,
  Button,
  TextInput,
  Select,
  Switch,
  Divider,
  Stack,
  Avatar,
  Badge,
  ActionIcon,
  Modal,
  PasswordInput,
  Textarea,
  NumberInput,
  Alert,
  Box,
  rem,
} from '@mantine/core';
import {
  IconUser,
  IconBell,
  IconShield,
  IconGlobe,
  IconKey,
  IconTrash,
  IconEdit,
  IconCheck,
  IconAlertTriangle,
  IconMoon,
  IconSun,
  IconMail,
  IconBrandDiscord,
  IconBrandTelegram,
  IconInfoCircle,
  IconPlus,
  IconX,
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper, IOSSectionHeader } from '@/components/UI/IOSCard';
import { useAppSelector } from '@/store';
import { useForm } from '@mantine/form';
import { notificationsService, NotificationSettings as NotificationSettingsType, NotificationDestination } from '@/services/api/notifications.service';

interface UserProfile {
  name: string;
  email: string;
  role: string;
  avatar?: string;
  bio: string;
  timezone: string;
  language: string;
}

interface GeneralNotificationSettings {
  alertNotifications: boolean;
  transactionNotifications: boolean;
  weeklyReports: boolean;
}

interface SecuritySettings {
  twoFactorEnabled: boolean;
  sessionTimeout: number;
  loginAlerts: boolean;
}

export default function Settings() {
  const user = useAppSelector((state) => state.auth.user);
  
  // Modal states
  const [profileModalOpened, setProfileModalOpened] = useState(false);
  const [passwordModalOpened, setPasswordModalOpened] = useState(false);
  const [deleteAccountModalOpened, setDeleteAccountModalOpened] = useState(false);
  
  // Settings states
  const [darkMode, setDarkMode] = useState(false);
  const [generalNotifications, setGeneralNotifications] = useState<GeneralNotificationSettings>({
    alertNotifications: true,
    transactionNotifications: false,
    weeklyReports: true,
  });

  const [notificationSettings, setNotificationSettings] = useState<NotificationSettingsType>({
    destinations: []
  });

  const [isSavingNotifications, setIsSavingNotifications] = useState(false);
  const [addDestinationModalOpened, setAddDestinationModalOpened] = useState(false);
  const [newDestinationType, setNewDestinationType] = useState<'email' | 'telegram' | 'discord'>('email');

  // Form for adding new destinations
  const newDestinationForm = useForm({
    initialValues: {
      name: '',
      address: '',
    },
    validate: {
      name: (value) => (value.trim().length < 1 ? 'Name is required' : null),
      address: (value, values, path) => {
        if (value.trim().length < 1) return 'Address is required';
        if (newDestinationType === 'email' && !value.includes('@')) {
          return 'Please enter a valid email address';
        }
        return null;
      },
    },
  });
  
  const [security, setSecurity] = useState<SecuritySettings>({
    twoFactorEnabled: false,
    sessionTimeout: 30,
    loginAlerts: true,
  });

  // Mock user profile
  const [profile, setProfile] = useState<UserProfile>({
    name: user?.email?.split('@')[0] || 'User',
    email: user?.email || 'user@example.com',
    role: 'Admin',
    bio: 'Blockchain enthusiast and team lead',
    timezone: 'UTC-8 (Pacific Time)',
    language: 'English',
  });

  // Load notification settings on mount
  useEffect(() => {
    const loadNotificationSettings = async () => {
      try {
        const settings = await notificationsService.getSettings();
        setNotificationSettings(settings);
      } catch (error) {
        console.error('Error loading notification settings:', error);
      }
    };

    loadNotificationSettings();
  }, []);

  const handleGeneralNotificationChange = (key: keyof GeneralNotificationSettings, value: boolean) => {
    setGeneralNotifications(prev => ({ ...prev, [key]: value }));
  };

  const handleSecurityChange = (key: keyof SecuritySettings, value: boolean | number) => {
    setSecurity(prev => ({ ...prev, [key]: value }));
  };

  const addDestination = (values: { name: string; address: string }) => {
    const newDestination: NotificationDestination = {
      id: Date.now().toString(),
      type: newDestinationType,
      name: values.name,
      address: values.address,
      enabled: true,
      created_at: new Date().toISOString(),
    };

    setNotificationSettings(prev => ({
      destinations: [...prev.destinations, newDestination]
    }));

    newDestinationForm.reset();
    setAddDestinationModalOpened(false);
  };

  const toggleDestination = (id: string) => {
    setNotificationSettings(prev => ({
      destinations: prev.destinations.map(dest =>
        dest.id === id ? { ...dest, enabled: !dest.enabled } : dest
      )
    }));
  };

  const removeDestination = (id: string) => {
    setNotificationSettings(prev => ({
      destinations: prev.destinations.filter(dest => dest.id !== id)
    }));
  };

  const saveNotificationSettings = async () => {
    setIsSavingNotifications(true);
    try {
      await notificationsService.saveSettings(notificationSettings);
      console.log('Notification settings saved successfully');
    } catch (error) {
      console.error('Error saving notification settings:', error);
    } finally {
      setIsSavingNotifications(false);
    }
  };

  const getDestinationIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <IconMail size={20} color="#007AFF" />;
      case 'telegram':
        return <IconBrandTelegram size={20} color="#0088cc" />;
      case 'discord':
        return <IconBrandDiscord size={20} color="#5865F2" />;
      default:
        return <IconBell size={20} />;
    }
  };

  const getDestinationsByType = (type: string) => {
    return notificationSettings.destinations.filter(dest => dest.type === type);
  };

  return (
    <IOSPageWrapper
      title="Settings"
      subtitle="Manage your account and preferences"
    >
      <Stack gap="xl">
        {/* Profile Section */}
        <IOSCard>
          <IOSSectionHeader
            title="Profile"
            subtitle="Manage your personal information"
            action={
              <ActionIcon
                variant="light"
                size="lg"
                onClick={() => setProfileModalOpened(true)}
              >
                <IconEdit size={18} />
              </ActionIcon>
            }
          />
          
          <Group p="md" gap="md">
            <Avatar size="xl" radius="xl">
              {profile.name.charAt(0).toUpperCase()}
            </Avatar>
            <Box style={{ flex: 1 }}>
              <Group gap="sm" mb="xs">
                <Text fw={600} size="lg">{profile.name}</Text>
                <Badge color="blue" variant="light">{profile.role}</Badge>
              </Group>
              <Text c="dimmed" size="sm" mb="xs">{profile.email}</Text>
              <Text size="sm">{profile.bio}</Text>
            </Box>
          </Group>
        </IOSCard>

        {/* Appearance Section */}
        <IOSCard>
          <IOSSectionHeader
            title="Appearance"
            subtitle="Customize your dashboard experience"
          />
          
          <Stack gap="md" p="md">
            <Group justify="space-between">
              <Group>
                <Box
                  style={{
                    padding: rem(8),
                    borderRadius: rem(8),
                    backgroundColor: '#f2f2f7',
                  }}
                >
                  {darkMode ? <IconMoon size={20} /> : <IconSun size={20} />}
                </Box>
                <Box>
                  <Text fw={500}>Dark Mode</Text>
                  <Text size="sm" c="dimmed">Switch between light and dark themes</Text>
                </Box>
              </Group>
              <Switch
                checked={darkMode}
                onChange={(event) => setDarkMode(event.currentTarget.checked)}
              />
            </Group>
            
            <Divider />
            
            <Group justify="space-between">
              <Group>
                <Box
                  style={{
                    padding: rem(8),
                    borderRadius: rem(8),
                    backgroundColor: '#f2f2f7',
                  }}
                >
                  <IconGlobe size={20} />
                </Box>
                <Box>
                  <Text fw={500}>Language</Text>
                  <Text size="sm" c="dimmed">Choose your preferred language</Text>
                </Box>
              </Group>
              <Select
                value={profile.language}
                onChange={(value) => setProfile(prev => ({ ...prev, language: value || 'English' }))}
                data={['English', 'Spanish', 'French', 'German', 'Chinese']}
                style={{ width: rem(120) }}
              />
            </Group>
          </Stack>
        </IOSCard>

        {/* General Notifications Section */}
        <IOSCard>
          <IOSSectionHeader
            title="General Notifications"
            subtitle="Control notification types and frequency"
          />

          <Stack gap="md" p="md">
            {Object.entries(generalNotifications).map(([key, value]) => (
              <Group key={key} justify="space-between">
                <Box>
                  <Text fw={500} tt="capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </Text>
                  <Text size="sm" c="dimmed">
                    {key === 'alertNotifications' && 'Wallet and price alerts'}
                    {key === 'transactionNotifications' && 'Transaction confirmations'}
                    {key === 'weeklyReports' && 'Weekly summary reports'}
                  </Text>
                </Box>
                <Switch
                  checked={value}
                  onChange={(event) =>
                    handleGeneralNotificationChange(key as keyof GeneralNotificationSettings, event.currentTarget.checked)
                  }
                />
              </Group>
            ))}
          </Stack>
        </IOSCard>

        {/* Notification Destinations Section */}
        <IOSCard>
          <IOSSectionHeader
            title="Notification Destinations"
            subtitle="Configure where you want to receive alerts"
            action={
              <Group gap="sm">
                <Button
                  size="sm"
                  variant="light"
                  leftSection={<IconPlus size={16} />}
                  onClick={() => setAddDestinationModalOpened(true)}
                >
                  Add Destination
                </Button>
                <Button
                  size="sm"
                  leftSection={<IconCheck size={16} />}
                  loading={isSavingNotifications}
                  onClick={saveNotificationSettings}
                  disabled={notificationSettings.destinations.length === 0}
                >
                  Save
                </Button>
              </Group>
            }
          />

          <Stack gap="lg" p="md">
            {notificationSettings.destinations.length === 0 ? (
              <Alert icon={<IconInfoCircle size={16} />} color="blue">
                No notification destinations configured. Click "Add Destination" to get started.
              </Alert>
            ) : (
              <>
                {/* Email Destinations */}
                {getDestinationsByType('email').length > 0 && (
                  <Box>
                    <Group gap="md" mb="md">
                      <Box
                        style={{
                          padding: rem(8),
                          borderRadius: rem(8),
                          backgroundColor: '#f2f2f7',
                        }}
                      >
                        <IconMail size={20} color="#007AFF" />
                      </Box>
                      <Box>
                        <Text fw={600}>Email Destinations</Text>
                        <Text size="sm" c="dimmed">
                          {getDestinationsByType('email').filter(d => d.enabled).length} of {getDestinationsByType('email').length} enabled
                        </Text>
                      </Box>
                    </Group>

                    <Stack gap="sm" ml="xl">
                      {getDestinationsByType('email').map((destination) => (
                        <Group key={destination.id} justify="space-between" p="sm" style={{ backgroundColor: '#f9f9f9', borderRadius: rem(8) }}>
                          <Box style={{ flex: 1 }}>
                            <Text fw={500}>{destination.name}</Text>
                            <Text size="sm" c="dimmed">{destination.address}</Text>
                          </Box>
                          <Group gap="xs">
                            <Switch
                              checked={destination.enabled}
                              onChange={() => toggleDestination(destination.id)}
                              size="sm"
                            />
                            <ActionIcon
                              variant="light"
                              color="red"
                              size="sm"
                              onClick={() => removeDestination(destination.id)}
                            >
                              <IconX size={14} />
                            </ActionIcon>
                          </Group>
                        </Group>
                      ))}
                    </Stack>
                  </Box>
                )}

                {/* Telegram Destinations */}
                {getDestinationsByType('telegram').length > 0 && (
                  <Box>
                    <Group gap="md" mb="md">
                      <Box
                        style={{
                          padding: rem(8),
                          borderRadius: rem(8),
                          backgroundColor: '#f2f2f7',
                        }}
                      >
                        <IconBrandTelegram size={20} color="#0088cc" />
                      </Box>
                      <Box>
                        <Text fw={600}>Telegram Destinations</Text>
                        <Text size="sm" c="dimmed">
                          {getDestinationsByType('telegram').filter(d => d.enabled).length} of {getDestinationsByType('telegram').length} enabled
                        </Text>
                      </Box>
                    </Group>

                    <Stack gap="sm" ml="xl">
                      {getDestinationsByType('telegram').map((destination) => (
                        <Group key={destination.id} justify="space-between" p="sm" style={{ backgroundColor: '#f9f9f9', borderRadius: rem(8) }}>
                          <Box style={{ flex: 1 }}>
                            <Text fw={500}>{destination.name}</Text>
                            <Text size="sm" c="dimmed">{destination.address}</Text>
                          </Box>
                          <Group gap="xs">
                            <Switch
                              checked={destination.enabled}
                              onChange={() => toggleDestination(destination.id)}
                              size="sm"
                            />
                            <ActionIcon
                              variant="light"
                              color="red"
                              size="sm"
                              onClick={() => removeDestination(destination.id)}
                            >
                              <IconX size={14} />
                            </ActionIcon>
                          </Group>
                        </Group>
                      ))}
                    </Stack>
                  </Box>
                )}

                {/* Discord Destinations */}
                {getDestinationsByType('discord').length > 0 && (
                  <Box>
                    <Group gap="md" mb="md">
                      <Box
                        style={{
                          padding: rem(8),
                          borderRadius: rem(8),
                          backgroundColor: '#f2f2f7',
                        }}
                      >
                        <IconBrandDiscord size={20} color="#5865F2" />
                      </Box>
                      <Box>
                        <Text fw={600}>Discord Destinations</Text>
                        <Text size="sm" c="dimmed">
                          {getDestinationsByType('discord').filter(d => d.enabled).length} of {getDestinationsByType('discord').length} enabled
                        </Text>
                      </Box>
                    </Group>

                    <Stack gap="sm" ml="xl">
                      {getDestinationsByType('discord').map((destination) => (
                        <Group key={destination.id} justify="space-between" p="sm" style={{ backgroundColor: '#f9f9f9', borderRadius: rem(8) }}>
                          <Box style={{ flex: 1 }}>
                            <Text fw={500}>{destination.name}</Text>
                            <Text size="sm" c="dimmed">{destination.address}</Text>
                          </Box>
                          <Group gap="xs">
                            <Switch
                              checked={destination.enabled}
                              onChange={() => toggleDestination(destination.id)}
                              size="sm"
                            />
                            <ActionIcon
                              variant="light"
                              color="red"
                              size="sm"
                              onClick={() => removeDestination(destination.id)}
                            >
                              <IconX size={14} />
                            </ActionIcon>
                          </Group>
                        </Group>
                      ))}
                    </Stack>
                  </Box>
                )}
              </>
            )}
          </Stack>
        </IOSCard>

        {/* Security Section */}
        <IOSCard>
          <IOSSectionHeader
            title="Security"
            subtitle="Protect your account and data"
          />
          
          <Stack gap="md" p="md">
            <Group justify="space-between">
              <Box>
                <Text fw={500}>Two-Factor Authentication</Text>
                <Text size="sm" c="dimmed">Add an extra layer of security</Text>
              </Box>
              <Switch
                checked={security.twoFactorEnabled}
                onChange={(event) => 
                  handleSecurityChange('twoFactorEnabled', event.currentTarget.checked)
                }
              />
            </Group>
            
            <Divider />
            
            <Group justify="space-between">
              <Box>
                <Text fw={500}>Session Timeout</Text>
                <Text size="sm" c="dimmed">Auto-logout after inactivity (minutes)</Text>
              </Box>
              <NumberInput
                value={security.sessionTimeout}
                onChange={(value) => handleSecurityChange('sessionTimeout', typeof value === 'number' ? value : 30)}
                min={5}
                max={120}
                style={{ width: rem(100) }}
              />
            </Group>
            
            <Divider />
            
            <Group justify="space-between">
              <Box>
                <Text fw={500}>Login Alerts</Text>
                <Text size="sm" c="dimmed">Get notified of new login attempts</Text>
              </Box>
              <Switch
                checked={security.loginAlerts}
                onChange={(event) => 
                  handleSecurityChange('loginAlerts', event.currentTarget.checked)
                }
              />
            </Group>
            
            <Divider />
            
            <Button
              variant="light"
              leftSection={<IconKey size={16} />}
              onClick={() => setPasswordModalOpened(true)}
            >
              Change Password
            </Button>
          </Stack>
        </IOSCard>

        {/* Danger Zone */}
        <IOSCard>
          <IOSSectionHeader
            title="Danger Zone"
            subtitle="Irreversible actions"
          />
          
          <Alert
            icon={<IconAlertTriangle size={16} />}
            color="red"
            variant="light"
            m="md"
          >
            <Text size="sm">
              These actions cannot be undone. Please proceed with caution.
            </Text>
          </Alert>
          
          <Box p="md">
            <Button
              color="red"
              variant="light"
              leftSection={<IconTrash size={16} />}
              onClick={() => setDeleteAccountModalOpened(true)}
            >
              Delete Account
            </Button>
          </Box>
        </IOSCard>
      </Stack>

      {/* Add Destination Modal */}
      <Modal
        opened={addDestinationModalOpened}
        onClose={() => {
          setAddDestinationModalOpened(false);
          newDestinationForm.reset();
        }}
        title="Add Notification Destination"
        size="md"
      >
        <form onSubmit={newDestinationForm.onSubmit(addDestination)}>
          <Stack gap="md">
            <Select
              label="Destination Type"
              placeholder="Select notification type"
              data={[
                { value: 'email', label: 'Email' },
                { value: 'telegram', label: 'Telegram' },
                { value: 'discord', label: 'Discord' },
              ]}
              value={newDestinationType}
              onChange={(value) => setNewDestinationType(value as 'email' | 'telegram' | 'discord')}
              leftSection={getDestinationIcon(newDestinationType)}
              required
            />

            <TextInput
              label="Name"
              placeholder="My Personal Email"
              description="A friendly name to identify this destination"
              required
              {...newDestinationForm.getInputProps('name')}
            />

            <TextInput
              label={
                newDestinationType === 'email' ? 'Email Address' :
                newDestinationType === 'telegram' ? 'Telegram Username or Chat ID' :
                'Discord Webhook URL'
              }
              placeholder={
                newDestinationType === 'email' ? 'your.email@example.com' :
                newDestinationType === 'telegram' ? '@username or 123456789' :
                'https://discord.com/api/webhooks/...'
              }
              description={
                newDestinationType === 'email' ? 'The email address to send notifications to' :
                newDestinationType === 'telegram' ? 'Your Telegram username (with @) or chat ID' :
                'Create a webhook in your Discord server settings'
              }
              required
              {...newDestinationForm.getInputProps('address')}
            />

            <Divider />

            <Group justify="flex-end">
              <Button
                variant="light"
                onClick={() => {
                  setAddDestinationModalOpened(false);
                  newDestinationForm.reset();
                }}
              >
                Cancel
              </Button>
              <Button type="submit" leftSection={<IconCheck size={16} />}>
                Add Destination
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </IOSPageWrapper>
  );
}
