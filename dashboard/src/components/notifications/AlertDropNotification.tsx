/**
 * Alert Drop Notification Component
 * 
 * Animated notification system with accessibility support
 * and Alert Drop elastic bounce effect
 */

import { forwardRef } from 'react'
import { 
  Paper, 
  Group, 
  Text, 
  CloseButton, 
  ThemeIcon,
  Stack,
  useMantineTheme,
  Badge,
} from '@mantine/core'
import { 
  IconAlertCircle, 
  IconAlertTriangle, 
  IconInfoCircle, 
  IconCheck,
  IconBell,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { NotificationProps } from '@mantine/notifications'

interface AlertDropNotificationProps extends NotificationProps {
  severity?: 'info' | 'warning' | 'error' | 'success' | 'critical'
  alertType?: string
  timestamp?: string
  soundEnabled?: boolean
}

const severityConfig = {
  info: {
    color: 'blue',
    icon: IconInfoCircle,
    sound: '/sounds/info.mp3',
  },
  warning: {
    color: 'yellow',
    icon: IconAlertTriangle,
    sound: '/sounds/warning.mp3',
  },
  error: {
    color: 'red',
    icon: IconAlertCircle,
    sound: '/sounds/error.mp3',
  },
  success: {
    color: 'green',
    icon: IconCheck,
    sound: '/sounds/success.mp3',
  },
  critical: {
    color: 'red',
    icon: IconBell,
    sound: '/sounds/critical.mp3',
  },
}

export const AlertDropNotification = forwardRef<
  HTMLDivElement,
  AlertDropNotificationProps
>(({ 
  severity = 'info',
  alertType,
  timestamp,
  soundEnabled = true,
  onClose,
  title,
  message,
  ...others 
}, ref) => {
  const theme = useMantineTheme()
  const config = severityConfig[severity]
  const Icon = config.icon

  // Play sound if enabled and not reduced motion
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  
  if (soundEnabled && !prefersReducedMotion && config.sound) {
    // Play notification sound
    const audio = new Audio(config.sound)
    audio.volume = 0.3
    audio.play().catch(() => {
      // Ignore audio play errors (e.g., autoplay blocked)
    })
  }

  return (
    <motion.div
      ref={ref}
      initial={{ 
        opacity: 0, 
        y: -100,
        scale: 0.3,
      }}
      animate={{ 
        opacity: 1, 
        y: 0,
        scale: 1,
      }}
      exit={{ 
        opacity: 0,
        x: 100,
        scale: 0.5,
      }}
      transition={{
        type: 'spring',
        stiffness: 500,
        damping: 25,
        mass: 0.5,
      }}
      style={{
        position: 'relative',
      }}
    >
      <Paper
        shadow="lg"
        p="md"
        radius="md"
        withBorder
        style={{
          borderLeft: `4px solid ${theme.colors[config.color][6]}`,
          backgroundColor: theme.white,
        }}
        {...others}
      >
        <Group position="apart" noWrap>
          <Group noWrap>
            <ThemeIcon
              size="lg"
              radius="xl"
              color={config.color}
              variant={severity === 'critical' ? 'filled' : 'light'}
            >
              <Icon size={20} />
            </ThemeIcon>
            <Stack spacing={4}>
              <Group spacing="xs">
                <Text size="sm" weight={500}>
                  {title}
                </Text>
                {alertType && (
                  <Badge size="xs" variant="dot" color={config.color}>
                    {alertType}
                  </Badge>
                )}
              </Group>
              {message && (
                <Text size="xs" color="dimmed">
                  {message}
                </Text>
              )}
              {timestamp && (
                <Text size="xs" color="dimmed">
                  {new Date(timestamp).toLocaleTimeString()}
                </Text>
              )}
            </Stack>
          </Group>
          {onClose && (
            <CloseButton
              size="sm"
              radius="xl"
              color={config.color}
              onClick={onClose}
              aria-label="Dismiss notification"
            />
          )}
        </Group>
      </Paper>
    </motion.div>
  )
})

AlertDropNotification.displayName = 'AlertDropNotification'

// Animation variants for different severities
export const alertDropVariants = {
  critical: {
    initial: { 
      opacity: 0, 
      y: -100,
      scale: 0.3,
      rotate: -180,
    },
    animate: { 
      opacity: 1, 
      y: 0,
      scale: 1,
      rotate: 0,
      transition: {
        type: 'spring',
        stiffness: 800,
        damping: 20,
        mass: 0.8,
      }
    },
  },
  normal: {
    initial: { 
      opacity: 0, 
      y: -50,
      scale: 0.8,
    },
    animate: { 
      opacity: 1, 
      y: 0,
      scale: 1,
      transition: {
        type: 'spring',
        stiffness: 500,
        damping: 25,
        mass: 0.5,
      }
    },
  },
}

// Notification container with AnimatePresence
export function AlertDropContainer({ children }: { children: React.ReactNode }) {
  return (
    <AnimatePresence mode="sync">
      {children}
    </AnimatePresence>
  )
}