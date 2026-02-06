/**
 * Simple Dashboard App - No Complex Components
 */

import React from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { 
  MantineProvider, 
  Button, 
  Stack, 
  Title, 
  Text, 
  Card, 
  Group,
  Badge,
  Container,
  Grid,
  Box
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

console.log('App-simple.tsx loading...')

function Navigation() {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Home', icon: IconHome },
    { path: '/dashboard', label: 'Dashboard', icon: IconDashboard },
    { path: '/alerts', label: 'Alerts', icon: IconBell },
    { path: '/profile', label: 'Profile', icon: IconUser },
  ]
  
  return (
    <Card shadow="sm" padding="md" radius="md" withBorder>
      <Group gap="md">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <Button
              key={item.path}
              component={Link}
              to={item.path}
              variant={location.pathname === item.path ? 'filled' : 'light'}
              leftSection={<Icon size={16} />}
            >
              {item.label}
            </Button>
          )
        })}
      </Group>
    </Card>
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
      
      <Grid>
        <Grid.Col span={4}>
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Stack gap="xs">
              <Text fw={500}>Active Alerts</Text>
              <Title order={1} c="blue">12</Title>
            </Stack>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={4}>
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Stack gap="xs">
              <Text fw={500}>Transactions</Text>
              <Title order={1} c="green">1,234</Title>
            </Stack>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={4}>
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Stack gap="xs">
              <Text fw={500}>Networks</Text>
              <Title order={1} c="purple">5</Title>
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>
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
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Card shadow="sm" padding="md" radius="md" withBorder>
          <Group justify="space-between">
            <Title order={1}>Ekko Dashboard</Title>
            <Badge color="green" size="lg">Working ✅</Badge>
          </Group>
        </Card>
        
        {/* Navigation */}
        <Navigation />
        
        {/* Main Content */}
        <Box>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/profile" element={<ProfilePage />} />
          </Routes>
        </Box>
      </Stack>
    </Container>
  )
}

function App() {
  console.log('Simple App component rendering...')
  
  return (
    <MantineProvider>
      <Notifications />
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </MantineProvider>
  )
}

console.log('App-simple.tsx loaded successfully!')

export default App
