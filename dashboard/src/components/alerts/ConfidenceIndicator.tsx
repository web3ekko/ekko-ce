/**
 * Confidence Indicator Component
 * 
 * Animated progress bar showing AI confidence level
 */

import { Box, Text, Progress, Group, Tooltip } from '@mantine/core'
import { IconBrain, IconAlertCircle, IconCheck } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'framer-motion'

interface ConfidenceIndicatorProps {
  confidence: number
}

export function ConfidenceIndicator({ confidence }: ConfidenceIndicatorProps) {
  const getColor = () => {
    if (confidence >= 85) return 'green'
    if (confidence >= 60) return 'yellow'
    return 'orange'
  }

  const getLabel = () => {
    if (confidence >= 85) return 'Very High'
    if (confidence >= 70) return 'High'
    if (confidence >= 60) return 'Good'
    if (confidence >= 40) return 'Moderate'
    return 'Low'
  }

  const getIcon = () => {
    if (confidence >= 85) return <IconCheck size={14} />
    if (confidence >= 60) return <IconBrain size={14} />
    return <IconAlertCircle size={14} />
  }

  const getMessage = () => {
    if (confidence >= 85) return 'I understand your request clearly'
    if (confidence >= 60) return 'I mostly understand, but could use more details'
    return 'Please provide more specific details'
  }

  return (
    <AnimatePresence mode="wait">
      {confidence > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: 0.2 }}
        >
          <Tooltip label={getMessage()} position="bottom">
            <Box style={{ minWidth: 180 }}>
              <Group gap="xs" mb={4}>
                <Box style={{ color: `var(--mantine-color-${getColor()}-6)` }}>
                  {getIcon()}
                </Box>
                <Text size="xs" fw={600}>
                  Confidence: {confidence}%
                </Text>
                <Text size="xs" c={getColor()} fw={500}>
                  {getLabel()}
                </Text>
              </Group>
              
              <Box style={{ position: 'relative' }}>
                <Progress
                  value={confidence}
                  color={getColor()}
                  size="sm"
                  radius="xl"
                  animate
                  styles={{
                    bar: {
                      transition: 'width 0.8s cubic-bezier(0.4, 0.0, 0.2, 1)',
                    },
                  }}
                />
                
                {/* Animated glow effect for high confidence */}
                {confidence >= 85 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: [0.3, 0.6, 0.3] }}
                    transition={{
                      duration: 2,
                      repeat: Infinity,
                      ease: "easeInOut",
                    }}
                    style={{
                      position: 'absolute',
                      inset: -2,
                      borderRadius: 12,
                      background: `radial-gradient(ellipse at center, var(--mantine-color-${getColor()}-4) 0%, transparent 70%)`,
                      pointerEvents: 'none',
                    }}
                  />
                )}
              </Box>
            </Box>
          </Tooltip>
        </motion.div>
      )}
    </AnimatePresence>
  )
}