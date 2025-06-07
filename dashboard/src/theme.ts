import { createTheme, rem } from '@mantine/core';

export const theme = createTheme({
  /** iOS-inspired theme with clean, modern design */

  // Color palette inspired by iOS design system
  colors: {
    // Primary blue (iOS system blue)
    blue: [
      '#f0f8ff',
      '#e6f3ff',
      '#cce7ff',
      '#99d6ff',
      '#66c2ff',
      '#007AFF', // iOS system blue
      '#0056cc',
      '#004499',
      '#003366',
      '#002244'
    ],

    // Neutral grays (iOS system grays)
    gray: [
      '#ffffff',
      '#f9f9f9',
      '#f2f2f7', // iOS system background
      '#e5e5ea', // iOS separator
      '#d1d1d6',
      '#8e8e93', // iOS secondary label
      '#6d6d70',
      '#48484a',
      '#3a3a3c',
      '#1c1c1e'  // iOS label
    ],

    // Success green (iOS system green)
    green: [
      '#f0fff4',
      '#e6ffed',
      '#ccf7d6',
      '#99f0b8',
      '#66e899',
      '#34C759', // iOS system green
      '#28a745',
      '#1e7e34',
      '#155724',
      '#0d3d1a'
    ],

    // Warning orange (iOS system orange)
    orange: [
      '#fff8f0',
      '#fff0e6',
      '#ffe0cc',
      '#ffcc99',
      '#ffb366',
      '#FF9500', // iOS system orange
      '#cc7700',
      '#995500',
      '#663300',
      '#441100'
    ],

    // Error red (iOS system red)
    red: [
      '#fff5f5',
      '#ffe6e6',
      '#ffcccc',
      '#ff9999',
      '#ff6666',
      '#FF3B30', // iOS system red
      '#cc2e24',
      '#992218',
      '#66170c',
      '#440b06'
    ]
  },

  // Typography with system fonts
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  fontFamilyMonospace: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',

  headings: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    fontWeight: '600',
    sizes: {
      h1: { fontSize: rem(34), lineHeight: '1.2' },
      h2: { fontSize: rem(28), lineHeight: '1.25' },
      h3: { fontSize: rem(22), lineHeight: '1.3' },
      h4: { fontSize: rem(20), lineHeight: '1.35' },
      h5: { fontSize: rem(18), lineHeight: '1.4' },
      h6: { fontSize: rem(16), lineHeight: '1.45' }
    }
  },

  // Spacing system (iOS uses 8pt grid)
  spacing: {
    xs: rem(4),
    sm: rem(8),
    md: rem(16),
    lg: rem(24),
    xl: rem(32)
  },

  // Border radius (iOS style)
  radius: {
    xs: rem(4),
    sm: rem(8),
    md: rem(12),
    lg: rem(16),
    xl: rem(20)
  },

  // Shadows (iOS style - subtle and layered)
  shadows: {
    xs: '0 1px 3px rgba(0, 0, 0, 0.05)',
    sm: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04)'
  },

  // Component overrides for iOS feel
  components: {
    Card: {
      defaultProps: {
        radius: 'md',
        shadow: 'sm',
        withBorder: true
      },
      styles: {
        root: {
          borderColor: '#e5e5ea',
          backgroundColor: '#ffffff',
          transition: 'all 0.2s ease'
        }
      }
    },

    Button: {
      defaultProps: {
        radius: 'md'
      },
      styles: {
        root: {
          fontWeight: 600,
          transition: 'all 0.2s ease',
          border: 'none'
        }
      }
    },

    TextInput: {
      defaultProps: {
        radius: 'md'
      },
      styles: {
        input: {
          borderColor: '#e5e5ea',
          backgroundColor: '#f2f2f7',
          transition: 'all 0.2s ease',
          '&:focus': {
            borderColor: '#007AFF',
            backgroundColor: '#ffffff'
          }
        }
      }
    },

    Modal: {
      defaultProps: {
        radius: 'lg',
        shadow: 'xl'
      },
      styles: {
        content: {
          backgroundColor: '#ffffff'
        },
        header: {
          backgroundColor: '#ffffff',
          borderBottom: '1px solid #e5e5ea'
        }
      }
    },

    Badge: {
      defaultProps: {
        radius: 'xl'
      },
      styles: {
        root: {
          fontWeight: 600,
          textTransform: 'none'
        }
      }
    }
  },

  // Other theme properties can be added here
});
