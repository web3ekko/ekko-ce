/**
 * Settings Page - Improved Version
 * 
 * Main settings dashboard with organized sections and premium UI
 */

import { useState } from 'react'
import {
  Container,
  Title,
  Grid,
  Card,
  Text,
  Group,
  Stack,
  Button,
  Badge,
  ActionIcon,
  Switch,
  Select,
  Tabs,
  Divider,
  Avatar,
  Alert,
  SimpleGrid,
  ThemeIcon,
} from '@mantine/core'
import {
  IconUser,
  IconShield,
  IconNotification,
  IconPalette,
  IconKey,
  IconCreditCard,
  IconBell,
  IconGlobe,
  IconChevronRight,
  IconAlertCircle,
  IconCheck,
  IconMail,
  IconPhone,
} from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'

export function SettingsPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<string | null>('general')

  const settingsCards = [
    {
      icon: IconUser,
      title: 'Profile',
      description: 'Manage your personal information and preferences',
      path: '/dashboard/profile',
      color: 'blue'
    },
    {
      icon: IconShield,
      title: 'Security',
      description: 'Password, 2FA, and security settings',
      path: '/dashboard/settings/security',
      color: 'green'
    },
    {
      icon: IconNotification,
      title: 'Notifications',
      description: 'Email, push, and alert preferences',
      path: '/dashboard/settings/notifications',
      color: 'orange'
    },
    {
      icon: IconPalette,
      title: 'Appearance',
      description: 'Theme, layout, and display options',
      path: '/dashboard/settings/appearance',
      color: 'violet'
    },
    {
      icon: IconKey,
      title: 'API Keys',
      description: 'Manage your API keys and integrations',
      path: '/dashboard/api',
      color: 'cyan'
    },
    {
      icon: IconCreditCard,
      title: 'Billing',
      description: 'Subscription, usage, and payment methods',
      path: '/dashboard/settings/billing',
      color: 'yellow'
    }
  ]

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Group justify="space-between">
          <div>
            <Title order={1} c="#0F172A">Settings</Title>
            <Text c="#475569" mt="xs">
              Manage your account settings and preferences
            </Text>
          </div>
        </Group>

        {/* Profile Summary Card */}
        <Card padding="lg" radius="md" withBorder>
          <Group justify="space-between" align="flex-start">
            <Group gap="lg">
              <Avatar
                size={80}
                radius="xl"
                src={null}
                color="blue"
                style={{ border: '4px solid #F8FAFC' }}
              >
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </Avatar>
              <div>
                <Group gap="xs" align="center">
                  <Title order={3} c="#0F172A">{user?.full_name}</Title>
                  <Badge variant="light" color="blue">Pro Plan</Badge>
                </Group>
                <Text c="#64748B" mb="xs">{user?.email}</Text>
                <Group gap="md">
                  <Group gap={4}>
                    <IconMail size={14} color="#94A3B8" />
                    <Text size="xs" c="#64748B">Verified</Text>
                  </Group>
                  <Group gap={4}>
                    <IconPhone size={14} color="#94A3B8" />
                    <Text size="xs" c="#64748B">Add Phone</Text>
                  </Group>
                </Group>
              </div>
            </Group>
            <Button variant="light" onClick={() => navigate('/dashboard/profile')}>
              Edit Profile
            </Button>
          </Group>
        </Card>

        <Tabs value={activeTab} onChange={setActiveTab}>
          <Tabs.List>
            <Tabs.Tab value="general">General</Tabs.Tab>
            <Tabs.Tab value="quick">Quick Settings</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="general" pt="xl">
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
              {settingsCards.map((card) => (
                <Card
                  key={card.path}
                  padding="lg"
                  radius="md"
                  withBorder
                  style={{
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onClick={() => navigate(card.path)}
                  styles={{
                    root: {
                      '&:hover': {
                        borderColor: `var(--mantine-color-${card.color}-6)`,
                        boxShadow: `0 4px 12px var(--mantine-color-${card.color}-1)`,
                        transform: 'translateY(-2px)',
                      }
                    }
                  }}
                >
                  <Group justify="space-between" mb="md" align="flex-start">
                    <ThemeIcon
                      size={40}
                      radius="md"
                      variant="light"
                      color={card.color}
                    >
                      <card.icon size={20} />
                    </ThemeIcon>
                    <IconChevronRight size={16} color="#94A3B8" />
                  </Group>

                  <Title order={4} mb={4} c="#0F172A">{card.title}</Title>
                  <Text size="sm" c="#64748B" lh={1.5}>
                    {card.description}
                  </Text>
                </Card>
              ))}
            </SimpleGrid>
          </Tabs.Panel>

          <Tabs.Panel value="quick" pt="xl">
            <Grid>
              <Grid.Col span={{ base: 12, lg: 8 }}>
                <Card padding="lg" radius="md" withBorder>
                  <Title order={3} mb="xl">Quick Settings</Title>

                  <Stack gap="lg">
                    <Group justify="space-between">
                      <div>
                        <Text fw={500} c="#0F172A">Email Notifications</Text>
                        <Text size="sm" c="#64748B">Receive alerts and updates via email</Text>
                      </div>
                      <Switch size="md" defaultChecked color="blue" />
                    </Group>

                    <Divider />

                    <Group justify="space-between">
                      <div>
                        <Text fw={500} c="#0F172A">Push Notifications</Text>
                        <Text size="sm" c="#64748B">Browser notifications for important alerts</Text>
                      </div>
                      <Switch size="md" defaultChecked color="blue" />
                    </Group>

                    <Divider />

                    <Group justify="space-between" align="center">
                      <div>
                        <Text fw={500} c="#0F172A">Language</Text>
                        <Text size="sm" c="#64748B">Select your preferred language</Text>
                      </div>
                      <Select
                        placeholder="Select language"
                        defaultValue="en"
                        data={[
                          { value: 'en', label: 'English' },
                          { value: 'es', label: 'Spanish' },
                          { value: 'fr', label: 'French' },
                          { value: 'de', label: 'German' },
                          { value: 'ja', label: 'Japanese' },
                        ]}
                        leftSection={<IconGlobe size={16} />}
                        style={{ width: 200 }}
                      />
                    </Group>

                    <Divider />

                    <Group justify="space-between" align="center">
                      <div>
                        <Text fw={500} c="#0F172A">Alert Frequency</Text>
                        <Text size="sm" c="#64748B">How often you want to receive digests</Text>
                      </div>
                      <Select
                        placeholder="Select frequency"
                        defaultValue="immediate"
                        data={[
                          { value: 'immediate', label: 'Immediate' },
                          { value: 'hourly', label: 'Hourly Digest' },
                          { value: 'daily', label: 'Daily Digest' },
                          { value: 'weekly', label: 'Weekly Summary' },
                        ]}
                        leftSection={<IconBell size={16} />}
                        style={{ width: 200 }}
                      />
                    </Group>
                  </Stack>
                </Card>
              </Grid.Col>

              <Grid.Col span={{ base: 12, lg: 4 }}>
                <Stack gap="md">
                  <Alert
                    icon={<IconAlertCircle size={16} />}
                    title="Security Recommendation"
                    color="blue"
                    variant="light"
                  >
                    <Text size="sm" mb="xs">
                      Enable two-factor authentication to secure your account.
                    </Text>
                    <Button
                      size="xs"
                      variant="white"
                      onClick={() => navigate('/dashboard/settings/security')}
                    >
                      Set up 2FA
                    </Button>
                  </Alert>

                  <Card padding="lg" radius="md" withBorder>
                    <Title order={4} mb="md">Account Status</Title>
                    <Stack gap="sm">
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">Plan</Text>
                        <Badge color="blue" variant="light">Pro</Badge>
                      </Group>
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">Member since</Text>
                        <Text size="sm" fw={500}>Nov 2023</Text>
                      </Group>
                      <Group justify="space-between">
                        <Text size="sm" c="#64748B">Status</Text>
                        <Badge color="green" variant="dot">Active</Badge>
                      </Group>
                    </Stack>
                  </Card>
                </Stack>
              </Grid.Col>
            </Grid>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Container>
  )
}
