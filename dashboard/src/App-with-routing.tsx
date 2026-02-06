/**
 * React App with Mantine UI + React Router
 */

import React from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { MantineProvider, Button, Stack, Title, Text, Card, Group, Badge } from '@mantine/core'
import { notifications, Notifications } from '@mantine/notifications'
import { IconCheck, IconHome, IconBell, IconUser } from '@tabler/icons-react'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

console.log('App-with-routing.tsx loading...')

function Navigation() {
  const location = useLocation()
  
  return (
    <Card shadow="sm" padding="md" radius="md" withBorder mb="xl">
      <Group gap="md">
        <Button 
          component={Link} 
          to="/" 
          variant={location.pathname === '/' ? 'filled' : 'light'}
          leftSection={<IconHome size={16} />}
        >
          Home
        </Button>
        <Button 
          component={Link} 
          to="/dashboard" 
          variant={location.pathname === '/dashboard' ? 'filled' : 'light'}
          leftSection={<IconBell size={16} />}
        >
          Dashboard
        </Button>
        <Button
          component={Link}
          to="/alerts"
          variant={location.pathname === '/alerts' ? 'filled' : 'light'}
          leftSection={<IconBell size={16} />}
        >
          Alerts
        </Button>
        <Button
          component={Link}
          to="/profile"
          variant={location.pathname === '/profile' ? 'filled' : 'light'}
          leftSection={<IconUser size={16} />}
        >
          Profile
        </Button>
      </Group>
    </Card>
  )
}

function HomePage() {
  const showNotification = () => {
    notifications.show({
      title: 'Welcome!',
      message: 'React Router + Mantine is working!',
      color: 'blue',
      icon: <IconCheck size={16} />,
    })
  }
  
  return (
    <Stack gap="md">
      <Title order={2}>🏠 Home Page</Title>
      <Text>Welcome to the dashboard test!</Text>
      <Button onClick={showNotification} leftSection={<IconCheck size={16} />}>
        Test Notification
      </Button>
    </Stack>
  )
}

function DashboardPage() {
  return (
    <Stack gap="md">
      <Title order={2}>📊 Dashboard</Title>
      <Text>This is the main dashboard page.</Text>
      <Badge color="green">Dashboard Active</Badge>
    </Stack>
  )
}

function AlertsPage() {
  return (
    <Stack gap="md">
      <Title order={2}>🚨 Alerts</Title>
      <Text>This is the alerts management page.</Text>
      <Badge color="orange">Alerts System</Badge>
    </Stack>
  )
}

function ProfilePage() {
  return (
    <Stack gap="md">
      <Title order={2}>👤 Profile</Title>
      <Text>This is the user profile page.</Text>
      <Badge color="teal">User Profile</Badge>
    </Stack>
  )
}

function AppContent() {
  console.log('AppContent component rendering...')
  
  return (
    <Stack gap="xl" p="xl">
      <Title order={1}>🎉 React + Mantine + Router Test</Title>
      
      <Navigation />
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </Card>
      
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Stack gap="md">
          <Title order={3}>Status Check</Title>
          <Stack gap="xs">
            <Text size="sm">✅ React is working</Text>
            <Text size="sm">✅ Mantine UI is working</Text>
            <Text size="sm">✅ React Router is working</Text>
            <Text size="sm">✅ Navigation is working</Text>
            <Text size="sm">✅ Icons are working</Text>
            <Text size="sm">✅ Notifications are working</Text>
          </Stack>
        </Stack>
      </Card>
    </Stack>
  )
}

function App() {
  console.log('App component rendering...')
  
  return (
    <MantineProvider>
      <Notifications />
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </MantineProvider>
  )
}

console.log('App-with-routing.tsx loaded, exporting App...')

export default App
