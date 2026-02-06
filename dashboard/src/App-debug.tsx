/**
 * Debug App Component - Minimal Version
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'

// Styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

// Simple test component
function TestPage() {
  console.log('TestPage rendering...')
  
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>🎉 Dashboard Debug Test</h1>
      <div style={{ marginTop: '20px' }}>
        <p>✅ React is rendering</p>
        <p>✅ Mantine is working</p>
        <p>✅ Routing is working</p>
        <p>✅ TypeScript is compiling</p>
      </div>
      
      <div style={{ marginTop: '20px' }}>
        <button 
          onClick={() => alert('JavaScript is working!')}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#007bff', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Test JavaScript
        </button>
      </div>

      <div style={{ marginTop: '20px' }}>
        <h3>Navigation Test:</h3>
        <ul>
          <li><a href="/dashboard">Dashboard</a></li>
          <li><a href="/alerts">Alerts</a></li>
          <li><a href="/auth/login">Login</a></li>
          <li><a href="/auth/signup">Signup</a></li>
        </ul>
      </div>
    </div>
  )
}

function DashboardPage() {
  console.log('DashboardPage rendering...')
  
  return (
    <div style={{ padding: '20px' }}>
      <h1>📊 Dashboard</h1>
      <p>This is the dashboard page</p>
      <a href="/">← Back to Test</a>
    </div>
  )
}

function AlertsPage() {
  console.log('AlertsPage rendering...')
  
  return (
    <div style={{ padding: '20px' }}>
      <h1>🚨 Alerts</h1>
      <p>This is the alerts page</p>
      <a href="/">← Back to Test</a>
    </div>
  )
}

function LoginPage() {
  console.log('LoginPage rendering...')
  
  return (
    <div style={{ padding: '20px' }}>
      <h1>🔐 Login</h1>
      <p>This is the login page</p>
      <a href="/">← Back to Test</a>
    </div>
  )
}

function App() {
  console.log('App component rendering...')
  
  return (
    <MantineProvider>
      <Notifications />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<TestPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/auth/login" element={<LoginPage />} />
          <Route path="*" element={<TestPage />} />
        </Routes>
      </BrowserRouter>
    </MantineProvider>
  )
}

export default App
