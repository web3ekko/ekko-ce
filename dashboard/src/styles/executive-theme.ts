/**
 * Executive Theme for Mantine UI
 * 
 * Premium, Dark-Mode First, Executive Interface
 * Deep Space backgrounds, Neon Accents, and Glassmorphism
 */

import { createTheme, rem } from '@mantine/core'

// ============================================================================
// COLOR PALETTE
// ============================================================================

// Primary: Electric Indigo (Vibrant & Trustworthy)
const ekkoPrimary = [
  '#e0e7ff', // 0
  '#c7d2fe', // 1
  '#a5b4fc', // 2
  '#818cf8', // 3
  '#6366f1', // 4
  '#4f46e5', // 5 - Main Brand
  '#4338ca', // 6
  '#3730a3', // 7
  '#312e81', // 8
  '#1e1b4b', // 9
] as const

// Secondary: Deep Violet (Rich & Regal)
const ekkoSecondary = [
  '#f5f3ff', // 0
  '#ede9fe', // 1
  '#ddd6fe', // 2
  '#c4b5fd', // 3
  '#a78bfa', // 4
  '#8b5cf6', // 5
  '#7c3aed', // 6 - Main Secondary
  '#6d28d9', // 7
  '#5b21b6', // 8
  '#4c1d95', // 9
] as const

// Backgrounds: Deep Space & Obsidian
const backgrounds = {
  app: '#0B0C15',      // Deepest background
  surface: '#13141C',  // Card background
  overlay: '#1A1B26',  // Elevated surface
  modal: '#232433',    // Modal background
}

// Status Colors (Neon Inspired)
const statusColors = {
  success: '#34D399', // Neon Emerald
  warning: '#FBBF24', // Cyber Amber
  error: '#F87171',   // Crimson Neon
  info: '#60A5FA',    // Electric Blue
}

// Chain Colors (Vibrant)
const chainColors = {
  ethereum: '#627EEA',
  bitcoin: '#F7931A',
  solana: '#14F195',
  polygon: '#8247E5',
}

// ============================================================================
// THEME DEFINITION
// ============================================================================

export const executiveTheme = createTheme({
  /** Primary color */
  primaryColor: 'ekko-primary',

  /** Font family */
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
  fontFamilyMonospace: 'SF Mono, Monaco, Inconsolata, Fira Code, monospace',

  /** Default radius */
  defaultRadius: 'md',

  /** Colors */
  colors: {
    'ekko-primary': ekkoPrimary as any,
    'ekko-secondary': ekkoSecondary as any,
    'dark': [
      '#C1C2C5', // 0
      '#A6A7AB', // 1
      '#909296', // 2
      '#5c5f66', // 3
      '#373A40', // 4
      '#2C2E33', // 5
      '#25262b', // 6
      backgrounds.modal,   // 7 - UI Elements
      backgrounds.surface, // 8 - Cards
      backgrounds.app,     // 9 - App Background
    ],
  },

  /** Shadows - Neon Glows */
  shadows: {
    xs: '0 1px 3px rgba(0, 0, 0, 0.5), 0 1px 2px rgba(0, 0, 0, 0.3)',
    sm: '0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -1px rgba(0, 0, 0, 0.3)',
    md: '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3)',
    lg: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.3)',
    xl: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',

    // Custom Glows
    glowPrimary: `0 0 20px ${rem(2)} rgba(79, 70, 229, 0.35)`,
    glowSuccess: `0 0 20px ${rem(2)} rgba(16, 185, 129, 0.35)`,
    glowError: `0 0 20px ${rem(2)} rgba(239, 68, 68, 0.35)`,
  },

  /** Radius values */
  radius: {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '24px',
  },

  /** Spacing */
  spacing: {
    xs: '8px',
    sm: '12px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },

  /** Headings */
  headings: {
    fontFamily: 'Inter, sans-serif',
    fontWeight: '700',
    sizes: {
      h1: { fontSize: '48px', lineHeight: '1.1' },
      h2: { fontSize: '36px', lineHeight: '1.2' },
      h3: { fontSize: '30px', lineHeight: '1.3' },
      h4: { fontSize: '24px', lineHeight: '1.4' },
      h5: { fontSize: '20px', lineHeight: '1.5' },
      h6: { fontSize: '16px', lineHeight: '1.5' },
    },
  },

  /** Other tokens */
  other: {
    // Glass morphism
    glass: {
      subtle: 'rgba(255, 255, 255, 0.03)',
      medium: 'rgba(255, 255, 255, 0.07)',
      strong: 'rgba(255, 255, 255, 0.12)',
      border: 'rgba(255, 255, 255, 0.08)',
      blur: '12px',
    },

    // Gradients
    gradients: {
      premium: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
      dark: 'linear-gradient(180deg, rgba(19, 20, 28, 0) 0%, rgba(19, 20, 28, 0.8) 100%)',
      glow: 'radial-gradient(circle at center, rgba(37, 99, 235, 0.15) 0%, rgba(0, 0, 0, 0) 70%)',
    },

    // Status Colors (Direct Access)
    status: statusColors,
    chains: chainColors,
  },

  /** Component Overrides */
  components: {
    Button: {
      defaultProps: {
        radius: 'md',
        fw: 600,
      },
      styles: {
        root: {
          transition: 'all 0.2s ease',
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)',
          },
        },
      },
    },

    Card: {
      defaultProps: {
        radius: 'lg',
        bg: 'dark.8',
      },
      styles: (theme: any) => ({
        root: {
          border: `1px solid ${theme.other.glass.border}`,
          backdropFilter: `blur(${theme.other.glass.blur})`,
        },
      }),
    },

    Paper: {
      defaultProps: {
        bg: 'dark.8',
      },
    },

    Badge: {
      defaultProps: {
        radius: 'sm',
        fw: 600,
      },
    },

    Modal: {
      styles: (theme: any) => ({
        content: {
          border: `1px solid ${theme.other.glass.border}`,
          backgroundColor: backgrounds.modal,
        },
        header: {
          backgroundColor: backgrounds.modal,
        },
      }),
    },
  },
})
