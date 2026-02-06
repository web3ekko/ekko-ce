/**
 * iOS-Style Input Component
 * 
 * Premium input with floating label and smooth animations
 */

import { useState, useRef, forwardRef } from 'react'
import { TextInput, Box, Text } from '@mantine/core'
import type { TextInputProps } from '@mantine/core'
import { motion, AnimatePresence } from 'framer-motion'

interface IOSInputProps extends Omit<TextInputProps, 'label'> {
  label: string
  icon?: React.ReactNode
  helperText?: string
  errorText?: string
}

export const IOSInput = forwardRef<HTMLInputElement, IOSInputProps>(
  ({ label, icon, helperText, errorText, value, onChange, onFocus, onBlur, ...props }, ref) => {
    const [isFocused, setIsFocused] = useState(false)
    const [hasValue, setHasValue] = useState(!!value)
    const inputRef = useRef<HTMLInputElement>(null)

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true)
      onFocus?.(e)
    }

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(false)
      setHasValue(!!e.target.value)
      onBlur?.(e)
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setHasValue(!!e.target.value)
      onChange?.(e)
    }

    const isFloating = isFocused || hasValue || !!value

    return (
      <Box style={{ position: 'relative', marginBottom: 'var(--space-4)' }}>
        {/* Floating Label */}
        <motion.div
          initial={false}
          animate={{
            top: isFloating ? -8 : 16,
            left: icon ? 44 : 16,
            fontSize: isFloating ? '12px' : '16px',
            color: isFocused 
              ? 'var(--ekko-primary)' 
              : errorText 
                ? 'var(--status-error)' 
                : 'var(--text-secondary)',
          }}
          transition={{
            duration: 0.2,
            ease: [0.4, 0, 0.2, 1],
          }}
          style={{
            position: 'absolute',
            backgroundColor: isFloating ? 'var(--color-background)' : 'transparent',
            padding: isFloating ? '0 4px' : 0,
            pointerEvents: 'none',
            zIndex: 2,
          }}
        >
          <Text component="span" fw={isFloating ? 500 : 400}>
            {label}
          </Text>
        </motion.div>

        {/* Input Container */}
        <Box
          style={{
            position: 'relative',
            borderRadius: 'var(--radius-md)',
            overflow: 'hidden',
          }}
        >
          {/* Background glow effect */}
          <motion.div
            initial={false}
            animate={{
              opacity: isFocused ? 1 : 0,
              scale: isFocused ? 1 : 0.95,
            }}
            transition={{
              duration: 0.3,
              ease: [0.4, 0, 0.2, 1],
            }}
            style={{
              position: 'absolute',
              inset: -2,
              background: 'var(--gradient-premium)',
              borderRadius: 'var(--radius-md)',
              filter: 'blur(8px)',
              opacity: 0.3,
              pointerEvents: 'none',
            }}
          />

          <TextInput
            ref={ref || inputRef}
            value={value}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            leftSection={icon}
            error={errorText}
            {...props}
            styles={{
              input: {
                height: 56,
                paddingLeft: icon ? 44 : 16,
                paddingTop: 20,
                paddingBottom: 4,
                fontSize: 16,
                fontWeight: 500,
                backgroundColor: 'var(--input-background)',
                border: `1px solid ${
                  errorText 
                    ? 'var(--status-error)' 
                    : isFocused 
                      ? 'var(--ekko-primary)' 
                      : 'var(--input-border)'
                }`,
                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                },
                '&::placeholder': {
                  opacity: 0,
                },
              },
              wrapper: {
                position: 'relative',
              },
              error: {
                marginTop: 4,
                fontSize: 12,
              },
            }}
          />
        </Box>

        {/* Helper Text */}
        <AnimatePresence>
          {(helperText || errorText) && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              <Text
                size="xs"
                c={errorText ? 'var(--status-error)' : 'var(--text-tertiary)'}
                mt={4}
              >
                {errorText || helperText}
              </Text>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>
    )
  }
)

IOSInput.displayName = 'IOSInput'