/**
 * Light-First Theme for Mantine UI
 *
 * Airy light-only design with blue primary, teal secondary, and soft neutrals
 * Professional, light-mode-first aesthetic for executive blockchain monitoring
 *
 * Design Philosophy:
 * - Primary: Blue (#2563EB) - Confident, legible action color
 * - No dark mode - optimized for professional daytime use
 * - Clean surfaces with subtle borders and shadows
 * - High contrast text for excellent readability
 */

import { createTheme } from '@mantine/core'

// Define color tuple type (10 shades from lightest to darkest)
type MantineColorsTuple = readonly [string, string, string, string, string, string, string, string, string, string]

// Define custom brand colors as Mantine color tuples (10 shades)
// Primary: Blue
const ekkoPrimary: MantineColorsTuple = [
  '#EFF6FF', // 0 - subtle backgrounds
  '#DBEAFE', // 1
  '#BFDBFE', // 2
  '#93C5FD', // 3
  '#60A5FA', // 4
  '#3B82F6', // 5 - light variant
  '#2563EB', // 6 - main brand color (blue)
  '#1D4ED8', // 7 - hover state
  '#1E40AF', // 8
  '#1E3A8A', // 9 - darkest
]

// Secondary: Teal (complementary)
const ekkoSecondary: MantineColorsTuple = [
  '#F0FDFA', // 0 - subtle background
  '#CCFBF1', // 1
  '#99F6E4', // 2
  '#5EEAD4', // 3
  '#2DD4BF', // 4
  '#14B8A6', // 5 - light variant
  '#0D9488', // 6 - main secondary (teal)
  '#0F766E', // 7 - hover
  '#115E59', // 8
  '#134E4A', // 9
]

// Neutral gray scale aligned with design tokens
const ekkoGray: MantineColorsTuple = [
  '#F8FAFD', // 0
  '#F1F4F9', // 1
  '#E6E9EE', // 2
  '#D6DDE5', // 3
  '#B8C2D0', // 4
  '#94A3B8', // 5
  '#64748B', // 6
  '#475569', // 7
  '#334155', // 8
  '#0F172A', // 9
]

// Blockchain-specific colors (vibrant for light mode)
const chainEthereum: MantineColorsTuple = [
  '#EEF2FF', // 0
  '#E0E7FF', // 1
  '#C7D2FE', // 2
  '#A5B4FC', // 3
  '#7C94F5', // 4
  '#627EEA', // 5 - main Ethereum blue
  '#5B72DB', // 6
  '#5366CC', // 7
  '#4A5AB8', // 8
  '#3F4E9F', // 9
]

const chainBitcoin: MantineColorsTuple = [
  '#FFF7ED', // 0
  '#FFEDD5', // 1
  '#FED7AA', // 2
  '#FDBA74', // 3
  '#FFAA4D', // 4
  '#F7931A', // 5 - main Bitcoin orange
  '#E88716', // 6
  '#D47C14', // 7
  '#BF7012', // 8
  '#A66310', // 9
]

const chainSolana: MantineColorsTuple = [
  '#ECFDF5', // 0
  '#D1FAE5', // 1
  '#A7F3D0', // 2
  '#6EE7B7', // 3
  '#4DFFB8', // 4
  '#00FFA3', // 5 - main Solana green
  '#00E693', // 6
  '#00C89A', // 7  - darker variant
  '#00AA82', // 8
  '#008C6A', // 9
]

export const lightTheme = createTheme({
  /** Primary color */
  primaryColor: 'ekko-primary',

  /** Color scheme - LIGHT ONLY */
  defaultColorScheme: 'light',

  /** Auto-contrast disabled - we control all colors manually */
  autoContrast: false,

  /** Font family (Inter for professional look) */
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
  fontFamilyMonospace: 'SF Mono, Monaco, Inconsolata, Fira Code, Roboto Mono, monospace',

  /** Line height - increased for readability */
  lineHeights: {
    xs: '1.4',
    sm: '1.45',
    md: '1.55',
    lg: '1.6',   // Default body text (increased from 1.5)
    xl: '1.65',
  },

  /** Default radius */
  defaultRadius: 'md',

  /** Custom colors */
  colors: {
    'ekko-primary': ekkoPrimary,
    'ekko-secondary': ekkoSecondary,
    gray: ekkoGray,
    'chain-ethereum': chainEthereum,
    'chain-bitcoin': chainBitcoin,
    'chain-solana': chainSolana,
  },

  /** Shadows - Multi-layer Stripe-style (light, subtle) */
  shadows: {
    xs: '0 1px 2px rgba(0, 0, 0, 0.04)',
    sm: '0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.02)',
    md: '0 4px 6px rgba(0, 0, 0, 0.04), 0 2px 4px rgba(0, 0, 0, 0.02)',
    lg: '0 10px 15px rgba(0, 0, 0, 0.06), 0 4px 6px rgba(0, 0, 0, 0.03)',
    xl: '0 20px 25px rgba(0, 0, 0, 0.08), 0 10px 10px rgba(0, 0, 0, 0.04)',
  },

  /** Radius values - Professional, tighter (density optimized) */
  radius: {
    xs: '4px',
    sm: '6px',    /* was 8px - tighter */
    md: '8px',    /* was 12px - tighter for cards */
    lg: '10px',   /* was 16px - tighter */
    xl: '12px',   /* was 20px - tighter */
  },

  /** Spacing - 4px grid (density optimized) */
  spacing: {
    xs: '8px',
    sm: '12px',
    md: '16px',
    lg: '20px',   /* was 24px - tighter */
    xl: '24px',   /* was 32px - tighter */
  },

  /** Font sizes */
  fontSizes: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
  },

  /** Headings configuration */
  headings: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
    fontWeight: '700',
    sizes: {
      h1: { fontSize: '48px', lineHeight: '1.2', fontWeight: '700' },
      h2: { fontSize: '36px', lineHeight: '1.3', fontWeight: '700' },
      h3: { fontSize: '30px', lineHeight: '1.4', fontWeight: '600' },
      h4: { fontSize: '24px', lineHeight: '1.5', fontWeight: '600' },
      h5: { fontSize: '20px', lineHeight: '1.6', fontWeight: '600' },
      h6: { fontSize: '18px', lineHeight: '1.6', fontWeight: '500' },
    },
  },

  /** Breakpoints for responsive design */
  breakpoints: {
    xs: '30em',  // 480px - Mobile landscape
    sm: '48em',  // 768px - Tablet
    md: '64em',  // 1024px - Small laptop
    lg: '80em',  // 1280px - Desktop
    xl: '96em',  // 1536px - Large desktop
  },

  /** Other custom tokens */
  other: {
    // Gradients - Subtle backgrounds for cards
    gradientCardDefault: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(250, 250, 251, 0.98) 100%)',
    gradientCardElevated: 'linear-gradient(135deg, rgba(255, 255, 255, 1) 0%, rgba(252, 252, 252, 1) 100%)',
    gradientCardInteractive: 'linear-gradient(135deg, rgba(37, 99, 235, 0.02) 0%, rgba(59, 130, 246, 0.02) 100%)',

    // Brand gradients - Bold for headers/CTAs
    gradientPremium: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
    gradientSuccess: 'linear-gradient(135deg, #0EA371 0%, #10B981 100%)',
    gradientWarning: 'linear-gradient(135deg, #F97316 0%, #FB923C 100%)',
    gradientError: 'linear-gradient(135deg, #DC2626 0%, #EF4444 100%)',

    // Chain-specific gradients
    gradientEthereum: 'linear-gradient(135deg, rgba(98, 126, 234, 0.05) 0%, rgba(98, 126, 234, 0.02) 100%)',
    gradientBitcoin: 'linear-gradient(135deg, rgba(247, 147, 26, 0.05) 0%, rgba(247, 147, 26, 0.02) 100%)',
    gradientSolana: 'linear-gradient(135deg, rgba(0, 255, 163, 0.05) 0%, rgba(0, 255, 163, 0.02) 100%)',

    // Colored shadows for brand elements
    shadowPrimary: '0 8px 18px rgba(37, 99, 235, 0.2), 0 4px 10px rgba(37, 99, 235, 0.12)',
    shadowPrimaryHover: '0 12px 22px rgba(37, 99, 235, 0.24), 0 6px 12px rgba(37, 99, 235, 0.16)',
    shadowSuccess: '0 6px 12px rgba(16, 185, 129, 0.18), 0 4px 10px rgba(16, 185, 129, 0.12)',
    shadowError: '0 6px 12px rgba(239, 68, 68, 0.2), 0 4px 10px rgba(239, 68, 68, 0.14)',

    // Animation durations
    durationFast: '150ms',
    durationNormal: '250ms',
    durationSlow: '350ms',

    // Chain colors (for direct usage)
    chainEthereum: '#627EEA',
    chainBitcoin: '#F7931A',
    chainSolana: '#00FFA3',
    chainAvalanche: '#E84142',
    chainPolygon: '#8247E5',

    // Status colors
    statusSuccess: '#10B981',
    statusWarning: '#FB923C',
    statusError: '#EF4444',
    statusInfo: '#2563EB',

    // Text colors
    textPrimary: '#0F172A',
    textSecondary: '#334155',
    textMuted: '#64748B',
    textSubtle: '#94A3B8',
    textAccent: '#2563EB',

    // Border colors
    borderSubtle: '#E6E9EE',
    borderDefault: '#D6DDE5',
    borderStrong: '#B8C2D0',
  },

  /** Component-specific styles */
  components: {
    AppShell: {
      styles: {
        main: {
          backgroundColor: '#F7F9FC',
        },
        header: {
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid #E6E9EE',
        },
        navbar: {
          backgroundColor: '#F7F9FC',
          borderRight: '1px solid #E6E9EE',
        },
      },
    },

    Button: {
      defaultProps: {
        radius: 'md',
        color: 'ekko-primary',
      },
      styles: {
        root: {
          fontWeight: 600,
          transition: 'all 250ms cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'translateY(-1px)',
          },
        },
      },
    },

    ActionIcon: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    ThemeIcon: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Loader: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Progress: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    SegmentedControl: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Switch: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Checkbox: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Radio: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Slider: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    RingProgress: {
      defaultProps: {
        rootColor: 'gray.2',
      },
    },

    NavLink: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Anchor: {
      defaultProps: {
        c: 'ekko-primary',
      },
    },

    Text: {
      defaultProps: {
        c: 'gray.8',
      },
      styles: {
        root: {
          letterSpacing: '-0.01em',
        },
      },
    },

    Title: {
      styles: (theme) => ({
        root: {
          color: theme.colors.gray[9],
          letterSpacing: '-0.02em',
          textWrap: 'balance',
        },
      }),
    },

    Card: {
      defaultProps: {
        radius: 'md',  /* was lg - tighter for density */
        shadow: 'sm',
        withBorder: true,
        p: 'md',  /* 16px default padding */
      },
      styles: {
        root: {
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.97) 0%, rgba(250, 250, 251, 0.99) 100%)',
          border: '1px solid var(--mantine-color-gray-2)',
          transition: 'all 200ms cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            borderColor: 'var(--mantine-color-gray-4)',
            boxShadow: '0 6px 12px rgba(0, 0, 0, 0.05), 0 3px 6px rgba(0, 0, 0, 0.02)',
            transform: 'translateY(-1px)',  /* subtle lift */
          },
        },
      },
    },

    Paper: {
      defaultProps: {
        radius: 'md',
        shadow: 'xs',
      },
      styles: {
        root: {
          backgroundColor: '#FFFFFF',
        },
      },
    },

    Input: {
      defaultProps: {
        radius: 'md',
      },
      styles: {
        input: {
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--mantine-color-gray-3)',
          color: '#0A0A0B',
          lineHeight: 1.6,
          '&:focus': {
            borderColor: 'var(--mantine-color-ekko-primary-6)',
            boxShadow: '0 0 0 3px var(--mantine-color-ekko-primary-0)',
          },
          '&::placeholder': {
            color: '#A1A1AA',
          },
        },
      },
    },

    TextInput: {
      defaultProps: {
        radius: 'md',
      },
    },

    PasswordInput: {
      defaultProps: {
        radius: 'md',
      },
    },

    Select: {
      defaultProps: {
        radius: 'md',
      },
    },

    Modal: {
      defaultProps: {
        radius: 'lg',
        shadow: 'xl',
        centered: true,
      },
      styles: {
        content: {
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--mantine-color-gray-2)',
        },
        header: {
          backgroundColor: '#FFFFFF',
          borderBottom: '1px solid var(--mantine-color-gray-2)',
        },
        overlay: {
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          backdropFilter: 'blur(4px)',
        },
      },
    },

    Notification: {
      defaultProps: {
        radius: 'md',
      },
      styles: {
        root: {
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--mantine-color-gray-3)',
          boxShadow: '0 10px 15px rgba(0, 0, 0, 0.06), 0 4px 6px rgba(0, 0, 0, 0.03)',
        },
      },
    },

    Table: {
      styles: (theme) => ({
        root: {
          backgroundColor: '#FFFFFF',
        },
        thead: {
          backgroundColor: '#FAFAFA',
          borderBottom: `2px solid ${theme.colors.gray[3]}`,
        },
        th: {
          color: theme.colors.gray[7],
          fontWeight: 600,
          fontSize: '13px',
          letterSpacing: '0.02em',
        },
        td: {
          color: theme.colors.gray[8],
          borderBottom: `1px solid ${theme.colors.gray[2]}`,
        },
        tr: {
          '&:hover': {
            backgroundColor: '#F9F9FB',
          },
        },
      }),
    },

    Badge: {
      defaultProps: {
        radius: 'sm',
        color: 'ekko-primary',
      },
      styles: {
        root: {
          fontWeight: 600,
        },
      },
    },

    Tabs: {
      defaultProps: {
        color: 'ekko-primary',
      },
      styles: {
        tab: {
          fontWeight: 500,
          '&[data-active]': {
            borderBottomColor: 'var(--mantine-color-ekko-primary-6)',
            color: 'var(--mantine-color-ekko-primary-6)',
          },
        },
      },
    },

    Menu: {
      defaultProps: {
        radius: 'md',
      },
      styles: {
        dropdown: {
          backgroundColor: '#FFFFFF',
          border: '1px solid #E6E9EE',
        },
        item: {
          '&[data-hovered]': {
            backgroundColor: '#EFF6FF',
          },
        },
      },
    },

    Tooltip: {
      defaultProps: {
        color: 'ekko-primary',
      },
    },

    Alert: {
      defaultProps: {
        radius: 'md',
      },
    },
  },
})

/**
 * Legacy color palette export for backward compatibility
 * Use Mantine theme colors instead where possible
 */
export const colors = {
  // Brand colors
  primary: '#2563EB',
  secondary: '#14B8A6',

  // Status colors (vibrant for light mode)
  success: '#10B981',
  warning: '#FB923C',
  error: '#EF4444',
  info: '#2563EB',

  // Neutral colors (light mode)
  gray: {
    50: '#F7F9FC',
    100: '#F1F4F9',
    200: '#E6E9EE',
    300: '#D6DDE5',
    400: '#B8C2D0',
    500: '#94A3B8',
    600: '#64748B',
    700: '#475569',
    800: '#334155',
    900: '#0F172A',
  },

  // Background colors
  background: {
    base: '#FFFFFF',
    surface: '#F7F9FC',
    elevated: '#FFFFFF',
  },

  // Blockchain colors
  chains: {
    ethereum: '#627EEA',
    bitcoin: '#F7931A',
    solana: '#00FFA3',
    avalanche: '#E84142',
    polygon: '#8247E5',
  },
}

/**
 * Common styles for reuse (density optimized for light mode)
 */
export const commonStyles = {
  // Layout
  container: {
    maxWidth: '1440px',
    margin: '0 auto',
    padding: '0 20px',  /* was 24px - tighter */
  },

  // Cards with Stripe-inspired styling (density optimized)
  card: {
    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.97) 0%, rgba(250, 250, 251, 0.99) 100%)',
    borderRadius: '8px',   /* was 12px - tighter */
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.02)',
    border: '1px solid #E6E9EE',
    padding: '16px',       /* was 24px - tighter */
  },

  // Compact card variant for dense layouts
  cardCompact: {
    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.97) 0%, rgba(250, 250, 251, 0.99) 100%)',
    borderRadius: '6px',
    boxShadow: '0 1px 2px rgba(0, 0, 0, 0.04)',
    border: '1px solid #E6E9EE',
    padding: '12px',
  },

  // Cards with colored left border (Stripe pattern)
  cardWithAccent: (color: string) => ({
    background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.97) 0%, rgba(250, 250, 251, 0.99) 100%)',
    borderRadius: '8px',   /* was 12px - tighter */
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.02)',
    border: '1px solid #E6E9EE',
    borderLeft: `3px solid ${color}`,  /* was 4px - slightly thinner */
    padding: '16px',       /* was 24px - tighter */
  }),

  // Forms
  formSection: {
    marginBottom: '20px',  /* was 24px - tighter */
  },

  // Section gaps
  sectionGap: '20px',
  cardGap: '16px',
  elementGap: '12px',

  // Text styles
  mutedText: {
    color: '#475569',
    fontSize: '13px',  /* was 14px - slightly smaller for density */
    lineHeight: 1.5,
  },

  highContrastText: {
    color: '#0F172A',
    fontSize: '14px',  /* was 16px - slightly smaller for density */
    lineHeight: 1.5,
  },
}
