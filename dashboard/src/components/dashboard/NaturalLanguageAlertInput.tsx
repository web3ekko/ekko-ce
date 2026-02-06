/**
 * Natural Language Alert Input Component
 * 
 * Persistent search-bar style input with placeholder rotation, expand animation.
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import {
  TextInput,
  Group,
  Stack,
  Card,
  Text,
  Badge,
  Tooltip,
  ActionIcon,
  Box,
  Loader
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconSearch,
  IconSparkles,
  IconBulb,
  IconSend,
  IconX,
  IconRobot,
  IconTemplate,
  IconArrowsExchange,
  IconShieldCheck,
  IconWallet,
  IconCoins
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useFocusWithin } from '@mantine/hooks'
import { useNavigate } from 'react-router-dom'
import { useWebSocketStore } from '../../store/websocket'

const FALLBACK_PLACEHOLDER = 'Describe the alert you want to create'

const CATEGORY_META: Record<string, { color: string; icon: typeof IconWallet; label: string }> = {
  wallet: { color: 'blue', icon: IconWallet, label: 'Wallet' },
  token: { color: 'teal', icon: IconCoins, label: 'Token' },
  contract: { color: 'orange', icon: IconShieldCheck, label: 'Contract' },
  protocol: { color: 'grape', icon: IconArrowsExchange, label: 'Protocol' },
  network: { color: 'green', icon: IconArrowsExchange, label: 'Network' },
  anomaly: { color: 'red', icon: IconShieldCheck, label: 'Anomaly' },
}

interface NaturalLanguageAlertInputProps {
  onInputClick?: () => void
}

export function NaturalLanguageAlertInput({ onInputClick }: NaturalLanguageAlertInputProps) {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [isProcessing, setIsProcessing] = useState(false)
  const [currentPlaceholder, setCurrentPlaceholder] = useState(0)

  const { ref: focusRef, focused } = useFocusWithin()
  const inputRef = useRef<HTMLInputElement>(null)
  const { isConnected } = useWebSocketStore()
  const examplePrompts = useMemo(() => ([
    'Alert me when my wallet receives more than 1 ETH',
    'Alert me when my balance drops below 0.5 ETH',
    'Alert me when gas spikes above 100 gwei',
    'Alert me when USDC transfers exceed $10,000',
  ]), [])
  const placeholders = useMemo(() => (
    examplePrompts.length > 0 ? examplePrompts : [FALLBACK_PLACEHOLDER]
  ), [examplePrompts])

  // Rotate placeholder examples
  useEffect(() => {
    if (focused || input.length > 0) return

    const interval = setInterval(() => {
      setCurrentPlaceholder(prev => (prev + 1) % placeholders.length)
    }, 3000)

    return () => clearInterval(interval)
  }, [focused, input, placeholders.length])

  useEffect(() => {
    if (currentPlaceholder >= placeholders.length) {
      setCurrentPlaceholder(0)
    }
  }, [currentPlaceholder, placeholders.length])

  // Generate suggestions as user types
  useEffect(() => {
    if (input.length < 3) {
      setSuggestions([])
      return
    }

    const timeoutId = setTimeout(() => {
      // Command Center Logic
      if (input.startsWith('/') || input.toLowerCase().startsWith('go')) {
        setSuggestions([
          'Go to Settings',
          'Go to Wallets',
          'Go to Developer API',
          'Go to Team'
        ].filter(s => s.toLowerCase().includes(input.toLowerCase().replace('/', ''))))
        return
      }

      const matches = examplePrompts
        .filter((text) => text.toLowerCase().includes(input.toLowerCase()))
        .slice(0, 3)

      setSuggestions(matches)
    }, 200)

    return () => clearTimeout(timeoutId)
  }, [input, examplePrompts])

  const handleSubmit = async () => {
    if (!input.trim()) return

    localStorage.setItem('alert_draft_v1', input)
    if (onInputClick) {
      onInputClick()
      return
    }

    setIsProcessing(true)
    notifications.show({
      title: 'Open Alert Builder',
      message: 'Use the full alert builder to review and save your alert.',
      color: 'blue',
    })
    setIsProcessing(false)
  }

  const handleSuggestionSelect = (suggestion: string) => {
    setInput(suggestion)
    setSuggestions([])
  }

  return (
    <Card shadow="xs" padding="sm" radius="sm" withBorder style={{ borderColor: '#E6E9EE' }}>
      <Stack gap="xs">
        {/* Header - compact */}
        <Group justify="space-between" align="center">
          <Group gap="xs">
            <IconRobot size={16} color="var(--mantine-color-blue-6)" />
            <Text fw={600} size="xs">
              Create Alert
            </Text>
            {isConnected && (
              <Badge size="xs" color="green" variant="dot">
                AI
              </Badge>
            )}
          </Group>

          <Tooltip label="Browse marketplace templates">
            <ActionIcon
              size="sm"
              variant="subtle"
              aria-label="Browse marketplace templates"
              onClick={() => navigate('/dashboard/marketplace')}
            >
              <IconTemplate size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>

        {/* Input area */}
        <motion.div
          ref={focusRef}
          animate={{
            scale: focused ? 1.02 : 1,
            boxShadow: focused
              ? '0 12px 30px rgba(37,99,235,0.16), 0 0 0 1px #2563EB'
              : '0 4px 12px rgba(15,23,42,0.06)'
          }}
          transition={{ duration: 0.2 }}
        >
          <TextInput
            ref={inputRef}
            value={input}
            onClick={onInputClick}
            readOnly={!!onInputClick}
            onChange={(e) => setInput(e.currentTarget.value)}
            placeholder={placeholders[currentPlaceholder] || FALLBACK_PLACEHOLDER}
            size="lg"
            radius="lg"
            leftSection={<IconSearch size={18} color="#475569" />}
            leftSectionWidth={42}
            rightSection={
              <Group gap="xs">
                {input.length > 0 && (
                  <Tooltip label="Clear input">
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={() => {
                        setInput('')
                        setSuggestions([])
                      }}
                    >
                      <IconX size={14} />
                    </ActionIcon>
                  </Tooltip>
                )}

                {isProcessing ? (
                  <Loader size="sm" />
                ) : (
                  <Tooltip label="Create alert">
                    <ActionIcon
                      size="lg"
                      variant="filled"
                      color="blue"
                      aria-label="Create alert"
                      disabled={!input.trim()}
                      onClick={handleSubmit}
                    >
                      <IconSend size={18} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
            }
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit()
              }
            }}
            styles={{
              input: {
                fontSize: '16px',
                padding: '14px 16px 14px 48px',
                border: '1px solid #E6E9EE',
                backgroundColor: '#FFFFFF',
                transition: 'all 0.2s ease',
              }
            }}
          />
        </motion.div>

        {/* AI Suggestions */}
        <AnimatePresence>
          {suggestions.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <Stack gap="xs">
                <Group gap="xs">
                  <IconSparkles size={14} color="var(--mantine-color-teal-6)" />
                  <Text size="xs" fw={500} c="teal">
                    AI Suggestions
                  </Text>
                </Group>

                <Group gap="xs" wrap="wrap">
                  {suggestions.map((suggestion, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ duration: 0.2, delay: index * 0.1 }}
                    >
                      <Badge
                        size="sm"
                        variant="light"
                        color={suggestion.startsWith('Go to') ? 'blue' : 'teal'}
                        style={{ cursor: 'pointer' }}
                        leftSection={suggestion.startsWith('Go to') ? <IconSearch size={12} /> : <IconBulb size={12} />}
                        onClick={() => handleSuggestionSelect(suggestion)}
                      >
                        {suggestion.length > 50
                          ? `${suggestion.substring(0, 50)}...`
                          : suggestion
                        }
                      </Badge>
                    </motion.div>
                  ))}
                </Group>
              </Stack>
            </motion.div>
          )}

          {/* Quick Action Chips - always visible when no suggestions */}
          {suggestions.length === 0 && !input && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
            >
              <Group gap="xs" mt="xs">
                {['Alert on ETH > $3k', 'Check Gas Fees', 'Go to Settings', 'Monitor Wallet'].map((action, i) => (
                  <Badge
                    key={i}
                    size="sm"
                    variant="outline"
                    color="gray"
                    style={{ cursor: 'pointer', fontWeight: 500 }}
                    onClick={() => setInput(action.startsWith('Go') ? action : `Alert me when ${action}`)}
                  >
                    {action}
                  </Badge>
                ))}
              </Group>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Status indicator */}
        {
          isConnected && (
            <Group justify="center" gap="xs">
              <Box
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: '#10b981',
                  animation: 'pulse 1.5s infinite'
                }}
              />
              <Text size="xs" c="teal.6" fw={500}>
                AI Processing Ready • Real-time suggestions enabled
              </Text>
            </Group>
          )
        }
      </Stack >
    </Card >
  )
}
