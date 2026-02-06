/**
 * Dashboard Layout Component
 * 
 * Main layout for authenticated dashboard pages
 */

import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  AppShell,
  Burger,
  Group,
  Title,
  NavLink,
  Avatar,
  Menu,
  Text,
  rem,
  Stack,
  Divider,
  Box,
  ActionIcon,
  Tooltip,
  Kbd,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconDashboard,
  IconBell,
  IconSettings,
  IconLogout,
  IconUser,
  IconWallet,
  IconCode,
  IconSearch,
  IconUsers,
  IconHelp,
  IconCreditCard,
  IconFolder,
  IconChartBar,
  IconLock,
  IconPlugConnected,
  IconShieldCheck,
  IconTemplate,
} from '@tabler/icons-react'
import { useAuthStore } from '../../store/auth'
import { NotificationCenter } from '../notifications/NotificationCenter'
import { ConnectionIndicator } from '../../providers/WebSocketProvider'
import { EkkoLogo } from '../brand/EkkoLogo'
import { CommandPalette, useCommandPalette } from '../search/CommandPalette'
export function DashboardLayout() {
  const [opened, { toggle }] = useDisclosure()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const commandPalette = useCommandPalette()

  const handleLogout = async () => {
    await logout()
    navigate('/auth/login')
  }

  const topNavigationSections = [
    {
      label: 'MAIN MENU',
      items: [
        { icon: IconDashboard, label: 'Dashboard', path: '/dashboard' },
        {
          icon: IconBell,
          label: 'Alerts',
          path: '/dashboard/alerts',
          children: [
            { icon: IconBell, label: 'All Alerts', path: '/dashboard/alerts' },
            { icon: IconFolder, label: 'Alert Groups', path: '/dashboard/alerts/groups' },
            { icon: IconTemplate, label: 'Marketplace', path: '/dashboard/marketplace' },
          ],
        },
        {
          icon: IconWallet,
          label: 'Wallets',
          path: '/dashboard/wallets',
          children: [
            { icon: IconWallet, label: 'All Wallets', path: '/dashboard/wallets' },
            { icon: IconFolder, label: 'Wallet Groups', path: '/dashboard/wallets/groups' },
            { icon: IconShieldCheck, label: 'Provider Wallets', path: '/dashboard/wallets/providers' },
          ],
        },
      ],
    },
    {
      label: 'DEVELOPER',
      items: [
        { icon: IconCode, label: 'Developer API', path: '/dashboard/api' },
        { icon: IconPlugConnected, label: 'Webhooks', path: '/dashboard/webhooks' }
      ],
    },
  ]

  const accountNavigation = {
    label: 'ACCOUNT',
    items: [
      { icon: IconUser, label: 'Profile', path: '/dashboard/profile' },
      { icon: IconUsers, label: 'Team', path: '/dashboard/team' },
      {
        icon: IconSettings,
        label: 'Settings',
        path: '/dashboard/settings',
        children: [
          { icon: IconSettings, label: 'General', path: '/dashboard/settings' },
          { icon: IconBell, label: 'Notifications', path: '/dashboard/settings/notifications' },
          { icon: IconLock, label: 'Security', path: '/dashboard/settings/security' },
          { icon: IconCreditCard, label: 'Billing', path: '/dashboard/settings/billing' },
        ],
      },
      { icon: IconHelp, label: 'Help & Support', path: '/dashboard/help' },
    ],
  }

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{
        width: 240,
        breakpoint: 'sm',
        collapsed: { mobile: !opened },
      }}
      padding="0"
      style={{ background: '#F8FAFC' }}
    >
      {/* Header - Compact */}
      <AppShell.Header style={{ borderBottom: '1px solid #E2E8F0', background: 'rgba(255, 255, 255, 0.95)', backdropFilter: 'blur(8px)' }}>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger
              opened={opened}
              onClick={toggle}
              hiddenFrom="sm"
              size="xs"
            />
            <Group gap={8} align="center" style={{ cursor: 'pointer' }} onClick={() => navigate('/dashboard')}>
              <EkkoLogo variant="icon" size={28} interactive />
              <Title order={4} visibleFrom="xs" style={{ margin: 0, fontSize: '1rem', fontWeight: 700, letterSpacing: '-0.025em', color: '#0F172A' }}>Ekko</Title>
            </Group>
          </Group>

          <Group gap="xs">
            {/* Search Button */}
            <Tooltip
              label={
                <Group gap={4}>
                  <Text size="xs">Search</Text>
                  <Kbd size="xs">⌘K</Kbd>
                </Group>
              }
              position="bottom"
            >
              <ActionIcon
                variant="light"
                color="gray"
                size="md"
                radius="md"
                onClick={commandPalette.open}
                style={{ border: '1px solid #E2E8F0' }}
              >
                <IconSearch size={16} />
              </ActionIcon>
            </Tooltip>

            {/* Connection Indicator */}
            <ConnectionIndicator />

            {/* Notification Center */}
            <NotificationCenter />

            <Divider orientation="vertical" h={20} color="gray.2" visibleFrom="sm" />

            {/* User menu */}
            <Menu shadow="lg" width={200} radius="sm" position="bottom-end" transitionProps={{ transition: 'pop-top-right' }}>
              <Menu.Target>
                <Group style={{ cursor: 'pointer' }} gap={6}>
                  <Avatar size="xs" radius="xl" src={null} color="blue">
                    {user?.first_name?.[0]}{user?.last_name?.[0]}
                  </Avatar>
                  <Box visibleFrom="md">
                    <Text size="xs" fw={600} c="#0F172A" lh={1.2}>
                      {user?.full_name}
                    </Text>
                  </Box>
                </Group>
              </Menu.Target>

              <Menu.Dropdown p="xs">
                <Menu.Label>Account</Menu.Label>
                <Menu.Item
                  leftSection={<IconUser style={{ width: rem(16), height: rem(16) }} />}
                  onClick={() => navigate('/dashboard/profile')}
                  style={{ borderRadius: 8 }}
                >
                  Profile
                </Menu.Item>
                <Menu.Item
                  leftSection={<IconSettings style={{ width: rem(16), height: rem(16) }} />}
                  onClick={() => navigate('/dashboard/settings')}
                  style={{ borderRadius: 8 }}
                >
                  Settings
                </Menu.Item>

                <Menu.Divider my="xs" />

                <Menu.Item
                  color="red"
                  leftSection={<IconLogout style={{ width: rem(16), height: rem(16) }} />}
                  onClick={handleLogout}
                  style={{ borderRadius: 8 }}
                >
                  Logout
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      {/* Sidebar Navigation - Compact */}
      <AppShell.Navbar p="xs" style={{ background: '#FFFFFF', borderRight: '1px solid #E2E8F0' }}>
        <AppShell.Section grow>
          <Stack gap="md" pt="xs">
            {topNavigationSections.map((section) => (
              <Box key={section.label}>
                <Text
                  size="xs"
                  fw={700}
                  c="#94A3B8"
                  tt="uppercase"
                  mb="sm"
                  px="sm"
                  style={{ letterSpacing: '0.05em' }}
                >
                  {section.label}
                </Text>
                <Stack gap={4}>
                  {section.items.map((item) => (
                    item.children ? (
                      <NavLink
                        key={item.path}
                        label={
                          <Text size="sm" fw={500}>{item.label}</Text>
                        }
                        leftSection={<item.icon size="1.1rem" stroke={1.5} />}
                        defaultOpened={location.pathname.startsWith(item.path)}
                        onClick={() => navigate(item.path)}
                        childrenOffset={32}
                        styles={{
                          root: {
                            borderRadius: 8,
                            color: '#475569',
                            '&:hover': { backgroundColor: '#F1F5F9', color: '#0F172A' },
                          },
                          children: { paddingLeft: 0 }
                        }}
                      >
                        {item.children.map((child) => (
                          <NavLink
                            key={child.path}
                            label={
                              <Text size="sm" fw={500}>{child.label}</Text>
                            }
                            leftSection={<child.icon size="1rem" stroke={1.5} />}
                            onClick={(event) => {
                              event.preventDefault()
                              navigate(child.path)
                              if (opened) toggle()
                            }}
                            active={location.pathname === child.path}
                            styles={{
                              root: {
                                borderRadius: 8,
                                marginTop: 2,
                                color: '#64748B',
                                '&[data-active]': {
                                  backgroundColor: '#EFF6FF',
                                  color: '#2563EB',
                                  fontWeight: 600,
                                  '&:hover': { backgroundColor: '#EFF6FF' },
                                },
                                '&:hover': { backgroundColor: '#F8FAFC', color: '#0F172A' },
                                paddingLeft: '2.5rem', // Indent subsections
                              }
                            }}
                          />
                        ))}
                      </NavLink>
                    ) : (
                      <NavLink
                        key={item.path}
                        href={item.path}
                        label={
                          <Text size="sm" fw={500}>{item.label}</Text>
                        }
                        leftSection={<item.icon size="1.1rem" stroke={1.5} />}
                        onClick={(event) => {
                          event.preventDefault()
                          navigate(item.path)
                          if (opened) toggle()
                        }}
                        active={location.pathname === item.path}
                        styles={{
                          root: {
                            borderRadius: 8,
                            color: '#475569',
                            '&[data-active]': {
                              backgroundColor: '#EFF6FF',
                              color: '#2563EB',
                              '&:hover': { backgroundColor: '#EFF6FF' },
                            },
                            '&:hover': { backgroundColor: '#F1F5F9', color: '#0F172A' },
                          }
                        }}
                      />
                    )
                  ))}
                </Stack>
              </Box>
            ))}
          </Stack>
        </AppShell.Section>

        <AppShell.Section>
          <Divider my="md" color="gray.2" />
          <Text
            size="xs"
            fw={700}
            c="#94A3B8"
            tt="uppercase"
            mb="sm"
            px="sm"
            style={{ letterSpacing: '0.05em' }}
          >
            {accountNavigation.label}
          </Text>
          <Stack gap={4}>
            {accountNavigation.items.map((item) =>
              item.children ? (
                <NavLink
                  key={item.path}
                  label={
                    <Text size="sm" fw={500}>{item.label}</Text>
                  }
                  leftSection={<item.icon size="1.1rem" stroke={1.5} />}
                  defaultOpened={location.pathname.startsWith(item.path)}
                  onClick={() => navigate(item.path)}
                  childrenOffset={32}
                  styles={{
                    root: {
                      borderRadius: 8,
                      color: '#475569',
                      '&:hover': { backgroundColor: '#F1F5F9', color: '#0F172A' },
                    },
                    children: { paddingLeft: 0 }
                  }}
                >
                  {item.children.map((child) => (
                    <NavLink
                      key={child.path}
                      label={
                        <Text size="sm" fw={500}>{child.label}</Text>
                      }
                      leftSection={<child.icon size="1rem" stroke={1.5} />}
                      onClick={(event) => {
                        event.preventDefault()
                        navigate(child.path)
                        if (opened) toggle()
                      }}
                      active={location.pathname === child.path}
                      styles={{
                        root: {
                          borderRadius: 8,
                          marginTop: 2,
                          color: '#64748B',
                          '&[data-active]': {
                            backgroundColor: '#EFF6FF',
                            color: '#2563EB',
                            fontWeight: 600,
                            '&:hover': { backgroundColor: '#EFF6FF' },
                          },
                          '&:hover': { backgroundColor: '#F8FAFC', color: '#0F172A' },
                        }
                      }}
                    />
                  ))}
                </NavLink>
              ) : (
                <NavLink
                  key={item.path}
                  href={item.path}
                  label={
                    <Text size="sm" fw={500}>{item.label}</Text>
                  }
                  leftSection={<item.icon size="1.1rem" stroke={1.5} />}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(item.path)
                    if (opened) toggle()
                  }}
                  active={location.pathname === item.path}
                  styles={{
                    root: {
                      borderRadius: 8,
                      color: '#475569',
                      '&[data-active]': {
                        backgroundColor: '#EFF6FF',
                        color: '#2563EB',
                        '&:hover': { backgroundColor: '#EFF6FF' },
                      },
                      '&:hover': { backgroundColor: '#F1F5F9', color: '#0F172A' },
                    }
                  }}
                />
              )
            )}
          </Stack>

          <Box mt="xl" px="xs">
            <Box
              p="md"
              style={{
                background: 'linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)',
                borderRadius: 16,
                border: '1px solid #BFDBFE'
              }}
            >
              <Stack gap="xs" align="center">
                <Text size="sm" fw={600} c="#1E40AF">Ekko Mobile</Text>
                <Text size="xs" c="#3B82F6" ta="center" lh={1.4}>
                  Scan to manage your assets on the go
                </Text>
                <Box
                  p={8}
                  bg="white"
                  style={{ borderRadius: 8, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                >
                  <img
                    src="/logos/qr-placeholder.svg"
                    alt="Download App"
                    style={{ width: 80, height: 80, display: 'block' }}
                  />
                </Box>
              </Stack>
            </Box>
          </Box>
        </AppShell.Section>
      </AppShell.Navbar>

      {/* Main Content - Responsive padding */}
      <AppShell.Main>
        <Box
          p={{ base: 'sm', sm: 'md', md: 'lg' }}
          style={{ maxWidth: 1600, margin: '0 auto', width: '100%' }}
        >
          <Outlet />
        </Box>
      </AppShell.Main>

      {/* Command Palette */}
      <CommandPalette
        opened={commandPalette.opened}
        onClose={commandPalette.close}
      />
    </AppShell>
  )
}
