import { createTheme } from '@mantine/core'

export const theme = createTheme({
  /** Primary color scheme */
  primaryColor: 'blue',
  
  /** Default color scheme */
  defaultColorScheme: 'light',
  
  /** Font family */
  fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
  fontFamilyMonospace: 'Monaco, Courier, monospace',
  
  /** Headings configuration */
  headings: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif',
    sizes: {
      h1: { fontSize: '2rem', lineHeight: '1.4' },
      h2: { fontSize: '1.75rem', lineHeight: '1.4' },
      h3: { fontSize: '1.5rem', lineHeight: '1.4' },
      h4: { fontSize: '1.25rem', lineHeight: '1.4' },
      h5: { fontSize: '1.125rem', lineHeight: '1.4' },
      h6: { fontSize: '1rem', lineHeight: '1.4' },
    },
  },
  
  /** Component default props and styles */
  components: {
    Button: {
      defaultProps: {
        size: 'md',
      },
    },
    
    TextInput: {
      defaultProps: {
        size: 'md',
      },
    },
    
    PasswordInput: {
      defaultProps: {
        size: 'md',
      },
    },
    
    Card: {
      defaultProps: {
        shadow: 'sm',
        radius: 'md',
        withBorder: true,
      },
    },
    
    Paper: {
      defaultProps: {
        shadow: 'xs',
        radius: 'md',
      },
    },
    
    Modal: {
      defaultProps: {
        centered: true,
        overlayProps: { backgroundOpacity: 0.55, blur: 3 },
      },
    },
    
    Notification: {
      defaultProps: {
        radius: 'md',
      },
    },
  },
  
  /** Spacing scale */
  spacing: {
    xs: '0.5rem',
    sm: '0.75rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
  },
  
  /** Border radius scale */
  radius: {
    xs: '0.25rem',
    sm: '0.375rem',
    md: '0.5rem',
    lg: '0.75rem',
    xl: '1rem',
  },
  
  /** Shadow scale */
  shadows: {
    xs: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    sm: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
    md: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    lg: '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
    xl: '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
  },
  
  /** Breakpoints for responsive design */
  breakpoints: {
    xs: '30em',  // 480px
    sm: '48em',  // 768px
    md: '64em',  // 1024px
    lg: '74em',  // 1184px
    xl: '90em',  // 1440px
  },
})

/** Color palette for custom usage */
export const colors = {
  // Brand colors
  primary: '#1c7ed6',
  secondary: '#495057',
  
  // Status colors
  success: '#51cf66',
  warning: '#ffd43b',
  error: '#ff6b6b',
  info: '#74c0fc',
  
  // Neutral colors
  gray: {
    50: '#f8f9fa',
    100: '#f1f3f4',
    200: '#e9ecef',
    300: '#dee2e6',
    400: '#ced4da',
    500: '#adb5bd',
    600: '#868e96',
    700: '#495057',
    800: '#343a40',
    900: '#212529',
  },
  
  // Background colors
  background: {
    light: '#ffffff',
    dark: '#1a1b1e',
    paper: '#f8f9fa',
  },
}

/** Common styles for reuse */
export const commonStyles = {
  // Layout
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '0 1rem',
  },
  
  // Cards
  card: {
    backgroundColor: 'white',
    borderRadius: '0.5rem',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
    border: '1px solid #e9ecef',
  },
  
  // Forms
  formSection: {
    marginBottom: '1.5rem',
  },
  
  // Buttons
  primaryButton: {
    backgroundColor: colors.primary,
    '&:hover': {
      backgroundColor: '#1864ab',
    },
  },
  
  // Text
  mutedText: {
    color: colors.gray[600],
    fontSize: '0.875rem',
  },
  
  // Loading states
  skeleton: {
    borderRadius: '0.25rem',
  },
}
