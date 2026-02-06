import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import App from './App.tsx'

// Import design system - Dark mode first
import './index.css'

// Import Mantine styles
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'

// Import animations
import './styles/animations.css'

// Import executive theme
import { lightTheme } from './styles/light-theme'

console.log('main.tsx loading...')

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <MantineProvider theme={lightTheme} defaultColorScheme="light">
      <Notifications />
      <App />
    </MantineProvider>
  </BrowserRouter>
)
