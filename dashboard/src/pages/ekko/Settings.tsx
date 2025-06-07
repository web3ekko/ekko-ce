import React, { useState } from 'react';
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
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper, IOSSectionHeader } from '@/components/UI/IOSCard';
import { useAppSelector } from '@/store';
import { useForm } from '@mantine/form';

interface UserProfile {
  name: string;
  email: string;
  role: string;
  avatar?: string;
  bio: string;
  timezone: string;
  language: string;
}

interface NotificationSettings {
  emailNotifications: boolean;
  pushNotifications: boolean;
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
  const [notifications, setNotifications] = useState<NotificationSettings>({
    emailNotifications: true,
    pushNotifications: true,
    alertNotifications: true,
    transactionNotifications: false,
    weeklyReports: true,
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

  const handleNotificationChange = (key: keyof NotificationSettings, value: boolean) => {
    setNotifications(prev => ({ ...prev, [key]: value }));
  };

  const handleSecurityChange = (key: keyof SecuritySettings, value: boolean | number) => {
    setSecurity(prev => ({ ...prev, [key]: value }));
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

        {/* Notifications Section */}
        <IOSCard>
          <IOSSectionHeader
            title="Notifications"
            subtitle="Control how you receive updates"
          />
          
          <Stack gap="md" p="md">
            {Object.entries(notifications).map(([key, value]) => (
              <Group key={key} justify="space-between">
                <Box>
                  <Text fw={500} tt="capitalize">
                    {key.replace(/([A-Z])/g, ' $1').trim()}
                  </Text>
                  <Text size="sm" c="dimmed">
                    {key === 'emailNotifications' && 'Receive updates via email'}
                    {key === 'pushNotifications' && 'Browser push notifications'}
                    {key === 'alertNotifications' && 'Wallet and price alerts'}
                    {key === 'transactionNotifications' && 'Transaction confirmations'}
                    {key === 'weeklyReports' && 'Weekly summary reports'}
                  </Text>
                </Box>
                <Switch
                  checked={value}
                  onChange={(event) => 
                    handleNotificationChange(key as keyof NotificationSettings, event.currentTarget.checked)
                  }
                />
              </Group>
            ))}
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
    </IOSPageWrapper>
  );
}
