/**
 * Enhanced Natural Language Input Component
 * 
 * Large textarea with voice input, rotating placeholders, and real-time feedback
 */

import { useState, useEffect, useRef } from 'react'
import {
  Textarea,
  ActionIcon,
  Group,
  Text,
  Loader,
  Tooltip,
  Box,
  Transition,
} from '@mantine/core'
import {
  IconMicrophone,
  IconMicrophoneOff,
  IconSparkles,
} from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'

interface NaturalLanguageInputEnhancedProps {
  value: string
  onChange: (value: string) => void
  isProcessing?: boolean
}

const placeholderExamples = [
  "Alert me when my ETH balance drops below $50,000",
  "Notify me if any wallet receives more than 100 SOL",
  "Tell me when gas fees exceed 100 gwei on Ethereum",
  "Alert on unusual activity in my main wallet",
  "Notify when BTC price crosses $45,000",
  "Track large transactions over $1M on my wallets",
  "Alert me when my AVAX staking rewards are ready",
  "Monitor whale movements above 1000 ETH",
]

export function NaturalLanguageInputEnhanced({
  value,
  onChange,
  isProcessing = false,
}: NaturalLanguageInputEnhancedProps) {
  const [isFocused, setIsFocused] = useState(false)
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [currentPlaceholder, setCurrentPlaceholder] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [charIndex, setCharIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Typewriter effect for placeholder
  useEffect(() => {
    if (!isFocused && value.length === 0) {
      const targetPlaceholder = placeholderExamples[placeholderIndex]
      
      if (charIndex < targetPlaceholder.length) {
        const timer = setTimeout(() => {
          setCurrentPlaceholder(targetPlaceholder.slice(0, charIndex + 1))
          setCharIndex(charIndex + 1)
        }, 50)
        return () => clearTimeout(timer)
      } else {
        // Wait before moving to next placeholder
        const timer = setTimeout(() => {
          setPlaceholderIndex((prev) => (prev + 1) % placeholderExamples.length)
          setCharIndex(0)
          setCurrentPlaceholder('')
        }, 3000)
        return () => clearTimeout(timer)
      }
    }
  }, [charIndex, placeholderIndex, isFocused, value])

  // Handle voice input
  const handleVoiceInput = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech recognition is not supported in your browser.')
      return
    }

    const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
    const recognition = new SpeechRecognition()

    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = 'en-US'

    if (isRecording) {
      recognition.stop()
      setIsRecording(false)
      return
    }

    recognition.start()
    setIsRecording(true)

    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0])
        .map((result) => result.transcript)
        .join('')

      onChange(transcript)
    }

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error)
      setIsRecording(false)
    }

    recognition.onend = () => {
      setIsRecording(false)
    }
  }

  // Character count color
  const getCharCountColor = () => {
    if (value.length < 10) return 'dimmed'
    if (value.length < 20) return 'orange'
    return 'green'
  }

  return (
    <Box>
      <Group justify="flex-end" mb="xs" style={{ minHeight: 24 }}>
        <Transition
          mounted={isProcessing}
          transition="fade"
          duration={200}
          timingFunction="ease"
        >
          {(styles) => (
            <Group
              data-testid="nlp-processing-indicator"
              gap={6}
              wrap="nowrap"
              style={{
                ...styles,
                padding: '4px 10px',
                borderRadius: 999,
                backgroundColor: 'var(--surface-subtle)',
                border: '1px solid var(--color-surface-active)',
              }}
            >
              <Loader size="xs" />
              <Text size="xs" c="dimmed">Understanding...</Text>
            </Group>
          )}
        </Transition>
      </Group>
      <Box style={{ position: 'relative' }} data-testid="nlp-input-surface">
      <motion.div
        animate={{
          scale: isFocused ? 1.02 : 1,
          boxShadow: isFocused 
            ? '0 4px 20px rgba(0, 0, 0, 0.1)' 
            : '0 2px 8px rgba(0, 0, 0, 0.05)',
        }}
        transition={{ duration: 0.2 }}
        style={{ borderRadius: 8, backgroundColor: 'var(--color-surface-elevated)' }}
      >
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.currentTarget.value)}
          onFocus={() => {
            setIsFocused(true)
            setCurrentPlaceholder('')
          }}
          onBlur={() => setIsFocused(false)}
          placeholder={currentPlaceholder}
          minRows={3}
          maxRows={8}
          autosize
          size="lg"
          radius="md"
          styles={{
            input: {
              fontSize: 18,
              lineHeight: 1.6,
              padding: '16px 60px 16px 16px',
              border: '1px solid var(--color-surface-active)',
              backgroundColor: 'var(--color-surface)',
              transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
              '&:focus': {
                borderColor: 'var(--mantine-color-blue-5)',
                backgroundColor: 'var(--color-surface-elevated)',
              },
              '&:hover': {
                borderColor: 'var(--color-surface-active)',
              },
            },
            wrapper: {
              position: 'relative',
            },
          }}
        />
      </motion.div>

      {/* Voice Input Button */}
      <Tooltip label={isRecording ? "Stop recording" : "Voice input"}>
        <ActionIcon
          size="lg"
          radius="xl"
          variant={isRecording ? 'filled' : 'subtle'}
          c={isRecording ? 'red' : 'blue'}
          onClick={handleVoiceInput}
          style={{
            position: 'absolute',
            right: 12,
            top: 12,
          }}
        >
          <AnimatePresence mode="wait">
            {isRecording ? (
              <motion.div
                key="recording"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
              >
                <IconMicrophoneOff size={20} />
              </motion.div>
            ) : (
              <motion.div
                key="not-recording"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
              >
                <IconMicrophone size={20} />
              </motion.div>
            )}
          </AnimatePresence>
        </ActionIcon>
      </Tooltip>

      {/* Voice Recording Animation */}
      <AnimatePresence>
        {isRecording && (
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            style={{
              position: 'absolute',
              inset: -4,
              borderRadius: 8,
              pointerEvents: 'none',
            }}
          >
            <Box
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: 8,
                border: '3px solid var(--mantine-color-red-5)',
                animation: 'pulse 1.5s infinite',
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
      </Box>

      {/* Character Count and Hint */}
      <Group justify="space-between" mt="xs" px="xs" wrap="wrap">
        <Group gap={4}>
          <IconSparkles size={14} style={{ opacity: 0.5 }} />
          <Text size="xs" c="dimmed">
            {isFocused ? "Describe what you want to monitor" : "AI-powered natural language"}
          </Text>
        </Group>

        <Group gap="xs" wrap="wrap" justify="flex-end">
          <Transition
            mounted={value.length > 0}
            transition="fade"
            duration={200}
            timingFunction="ease"
          >
            {(styles) => (
              <Text size="xs" c={getCharCountColor()} style={styles}>
                {value.length} characters
              </Text>
            )}
          </Transition>
        </Group>
      </Group>

      <style>{`
        @keyframes pulse {
          0% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.5;
            transform: scale(1.02);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }
      `}</style>
    </Box>
  )
}
