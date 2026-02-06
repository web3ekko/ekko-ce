/**
 * Working Dashboard App - Clean Foundation
 */

import React from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import {
  MantineProvider,
  AppShell,
  Button,
  Stack,
  Title,
  Text,
  Card,
  Group,
  Badge,
  Container
} from '@mantine/core'
import { notifications, Notifications } from '@mantine/notifications'
import { 
  IconHome, 
  IconBell, 
  IconUser, 
  IconDashboard,
  IconCheck 
} from '@tabler/icons-react'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

console.log('App-working.tsx loading...')

function Navigation() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Home', icon: IconHome },
    { path: '/dashboard', label: 'Dashboard', icon: IconDashboard },
    { path: '/alerts', label: 'Alerts', icon: IconBell },
    { path: '/profile', label: 'Profile', icon: IconUser },
  ]
  
  return (
    <Stack gap="xs" p="md">
      {navItems.map((item) => {
        const Icon = item.icon
        return (
          <Button
            key={item.path}
            component={Link}
            to={item.path}
            variant={location.pathname === item.path ? 'filled' : 'subtle'}
            leftSection={<Icon size={16} />}
            justify="flex-start"
            fullWidth
          >
            {item.label}
          </Button>
        )
      })}
    </Stack>
  )
}

function HomePage() {
  const showNotification = () => {
    notifications.show({
      title: 'Welcome!',
      message: 'Dashboard is working perfectly!',
      color: 'blue',
      icon: <IconCheck size={16} />,
    })
  }
  
  return (
    <Stack gap="md">
      <Title order={2}>🏠 Welcome to Ekko Dashboard</Title>
      <Text>Your blockchain monitoring dashboard is ready!</Text>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>System Status</Title>
          <Group gap="md">
            <Badge color="green">React ✅</Badge>
            <Badge color="green">Mantine ✅</Badge>
            <Badge color="green">Router ✅</Badge>
            <Badge color="green">Icons ✅</Badge>
          </Group>
          <Button 
            onClick={showNotification} 
            leftSection={<IconCheck size={16} />}
            variant="light"
          >
            Test Notification
          </Button>
        </Stack>
      </Card>
    </Stack>
  )
}

function DashboardPage() {
  return (
    <Stack gap="md">
      <Title order={2}>📊 Dashboard</Title>
      <Text>Main dashboard with blockchain monitoring overview.</Text>
      
      <Group gap="md">
        <Card shadow="sm" padding="lg" radius="md" withBorder style={{ flex: 1 }}>
          <Stack gap="xs">
            <Text fw={500}>Active Alerts</Text>
            <Title order={1} c="blue">12</Title>
          </Stack>
        </Card>
        
        <Card shadow="sm" padding="lg" radius="md" withBorder style={{ flex: 1 }}>
          <Stack gap="xs">
            <Text fw={500}>Transactions</Text>
            <Title order={1} c="green">1,234</Title>
          </Stack>
        </Card>
        
        <Card shadow="sm" padding="lg" radius="md" withBorder style={{ flex: 1 }}>
          <Stack gap="xs">
            <Text fw={500}>Networks</Text>
            <Title order={1} c="purple">5</Title>
          </Stack>
        </Card>
      </Group>
    </Stack>
  )
}

function AlertsPage() {
  return (
    <Stack gap="md">
      <Title order={2}>🚨 Alert Management</Title>
      <Text>Manage your blockchain monitoring alerts.</Text>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Group justify="space-between">
            <Title order={3}>Recent Alerts</Title>
            <Button size="sm">Create Alert</Button>
          </Group>
          <Text size="sm" c="dimmed">
            Alert management system ready for implementation.
          </Text>
        </Stack>
      </Card>
    </Stack>
  )
}

function ProfilePage() {
  return (
    <Stack gap="md">
      <Title order={2}>👤 User Profile</Title>
      <Text>Manage your account settings and preferences.</Text>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>Account Information</Title>
          <Text size="sm" c="dimmed">
            Profile management ready for implementation.
          </Text>
        </Stack>
      </Card>
    </Stack>
  )
}

function AppContent() {
  return (
    <AppShell
      navbar={{ width: 250, breakpoint: 'sm' }}
      header={{ height: 60 }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={3}>Ekko Dashboard</Title>
          <Badge color="green">Working ✅</Badge>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar>
        <Navigation />
      </AppShell.Navbar>

      <AppShell.Main>
        <Container size="xl">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </Container>
      </AppShell.Main>
    </AppShell>
  )
}

function App() {
  console.log('Working App component rendering...')
  
  return (
    <MantineProvider>
      <Notifications />
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </MantineProvider>
  )
}

console.log('App-working.tsx loaded successfully!')

export default App
