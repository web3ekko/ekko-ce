/**
 * Executive Card Component
 *
 * Light-first executive card with clean surfaces and subtle depth.
 */

import { forwardRef } from 'react'
import { Box } from '@mantine/core'
import type { BoxProps } from '@mantine/core'
import { motion } from 'framer-motion'

interface ExecutiveCardProps extends Omit<BoxProps, 'ref'> {
  variant?: 'glass' | 'gradient' | 'solid' | 'elevated' | 'subtle'
  size?: 'compact' | 'default' | 'spacious' | 'hero'
  minHeight?: number | string
  glowOnHover?: boolean
  children: React.ReactNode
}

export const ExecutiveCard = forwardRef<HTMLDivElement, ExecutiveCardProps>(
  ({ variant = 'glass', size = 'default', minHeight, glowOnHover = true, children, className, ...props }, ref) => {
    const getVariantStyles = () => {
      switch (variant) {
        case 'gradient':
          return {
            background: 'var(--gradient-card-interactive)',
            border: '1px solid var(--card-border)',
          }
        case 'solid':
          return {
            background: 'var(--color-surface-elevated)',
            border: '1px solid var(--card-border)',
          }
        case 'elevated':
          return {
            background: 'var(--card-bg-elevated)',
            border: '1px solid var(--card-border)',
          }
        case 'subtle':
          return {
            background: 'var(--surface-subtle)',
            border: '1px solid var(--card-border)',
          }
        case 'glass':
        default:
          return {
            background: 'var(--card-bg)',
            border: '1px solid var(--card-border)',
          }
      }
    }

    const getSizeStyles = () => {
      switch (size) {
        case 'compact':
          return {
            padding: 'var(--card-padding-compact)',
            minHeight: minHeight || 'var(--card-height-compact)',
          }
        case 'spacious':
          return {
            padding: 'var(--card-padding-spacious)',
            minHeight: minHeight || 'var(--card-height-spacious)',
          }
        case 'hero':
          return {
            padding: 'var(--card-padding-hero)',
            minHeight: minHeight || 'var(--card-height-hero)',
          }
        case 'default':
        default:
          return {
            padding: 'var(--card-padding-default)',
            minHeight: minHeight || 'auto',
          }
      }
    }

    const baseStyles = {
      borderRadius: 'var(--radius-md)',  /* was lg - tighter for density */
      boxShadow: 'var(--card-shadow)',
      position: 'relative' as const,
      overflow: 'hidden',
      ...getVariantStyles(),
      ...getSizeStyles(),
    }

    const hoverStyles = glowOnHover ? {
      boxShadow: 'var(--card-shadow-hover)',
      transform: 'translateY(-1px)',
      borderColor: 'var(--card-border-hover)',
    } : {}

    return (
      <Box
        component={motion.div}
        ref={ref}
        className={`executive-card ${className || ''}`}
        initial={{ opacity: 0, y: 8 }}    /* was y: 20 - subtler entrance */
        animate={{ opacity: 1, y: 0 }}
        whileHover={hoverStyles}
        transition={{
          duration: 0.2,               /* was 0.3 - snappier */
          ease: [0.4, 0, 0.2, 1],
        }}
        {...props}
        style={{
          ...baseStyles,
          ...props.style,
        }}
      >
        {/* Content */}
        <Box style={{ position: 'relative', zIndex: 1 }}>
          {children}
        </Box>
      </Box>
    )
  }
)

ExecutiveCard.displayName = 'ExecutiveCard'
