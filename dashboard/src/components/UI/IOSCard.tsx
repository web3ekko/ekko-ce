import React from 'react';
import { Card, CardProps, Box, rem, Container, Group, Text } from '@mantine/core';

interface IOSCardProps extends CardProps {
  children: React.ReactNode;
  interactive?: boolean;
  elevated?: boolean;
  glassy?: boolean;
  onClick?: () => void;
}

export const IOSCard: React.FC<IOSCardProps> = ({
  children,
  interactive = false,
  elevated = false,
  glassy = false,
  onClick,
  style,
  ...props
}) => {
  const baseStyles = {
    borderRadius: rem(16),
    border: '1px solid rgba(229, 229, 234, 0.6)',
    backgroundColor: glassy ? 'rgba(255, 255, 255, 0.8)' : '#ffffff',
    backdropFilter: glassy ? 'blur(20px)' : 'none',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    overflow: 'hidden' as const,
  };

  const interactiveStyles = interactive
    ? {
        cursor: 'pointer',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: elevated
            ? '0 20px 40px rgba(0, 0, 0, 0.1), 0 8px 16px rgba(0, 0, 0, 0.06)'
            : '0 8px 25px rgba(0, 0, 0, 0.08), 0 4px 10px rgba(0, 0, 0, 0.04)',
          borderColor: 'rgba(0, 122, 255, 0.2)',
        },
        '&:active': {
          transform: 'translateY(0px)',
          transition: 'all 0.1s cubic-bezier(0.4, 0, 0.2, 1)',
        },
      }
    : {};

  const elevatedStyles = elevated
    ? {
        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04)',
      }
    : {
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03)',
      };

  return (
    <Card
      {...props}
      onClick={onClick}
      style={{
        ...baseStyles,
        ...elevatedStyles,
        ...interactiveStyles,
        ...style,
      }}
    >
      {children}
    </Card>
  );
};

// Specialized card variants
export const IOSStatsCard: React.FC<{
  children: React.ReactNode;
  onClick?: () => void;
}> = ({ children, onClick }) => (
  <IOSCard interactive={!!onClick} elevated onClick={onClick}>
    <Box p="lg">{children}</Box>
  </IOSCard>
);

export const IOSContentCard: React.FC<{
  children: React.ReactNode;
  glassy?: boolean;
}> = ({ children, glassy = false }) => (
  <IOSCard glassy={glassy} elevated>
    <Box p="xl">{children}</Box>
  </IOSCard>
);

export const IOSListCard: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => (
  <IOSCard>
    <Box>{children}</Box>
  </IOSCard>
);

// iOS-style section header
export const IOSSectionHeader: React.FC<{
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}> = ({ title, subtitle, action }) => (
  <Box
    style={{
      padding: `${rem(8)} ${rem(16)}`,
      backgroundColor: 'transparent',
    }}
  >
    <Box
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <Box>
        <Box
          component="h3"
          style={{
            margin: 0,
            fontSize: rem(22),
            fontWeight: 700,
            color: '#1c1c1e',
            lineHeight: 1.2,
          }}
        >
          {title}
        </Box>
        {subtitle && (
          <Box
            component="p"
            style={{
              margin: `${rem(4)} 0 0 0`,
              fontSize: rem(15),
              color: '#8e8e93',
              lineHeight: 1.3,
            }}
          >
            {subtitle}
          </Box>
        )}
      </Box>
      {action && <Box>{action}</Box>}
    </Box>
  </Box>
);

// iOS-style divider
export const IOSDivider: React.FC = () => (
  <Box
    style={{
      height: '1px',
      backgroundColor: '#e5e5ea',
      margin: `0 ${rem(16)}`,
    }}
  />
);

// iOS-style list item
export const IOSListItem: React.FC<{
  children: React.ReactNode;
  onClick?: () => void;
  showChevron?: boolean;
}> = ({ children, onClick, showChevron = false }) => (
  <Box
    style={{
      padding: `${rem(12)} ${rem(16)}`,
      cursor: onClick ? 'pointer' : 'default',
      transition: 'background-color 0.2s ease',
      '&:hover': onClick
        ? {
            backgroundColor: '#f2f2f7',
          }
        : {},
      '&:active': onClick
        ? {
            backgroundColor: '#e5e5ea',
          }
        : {},
    }}
    onClick={onClick}
  >
    <Box
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <Box style={{ flex: 1 }}>{children}</Box>
      {showChevron && (
        <Box
          style={{
            marginLeft: rem(8),
            color: '#8e8e93',
          }}
        >
          <svg width="8" height="13" viewBox="0 0 8 13" fill="currentColor">
            <path d="M1.5 1L6.5 6.5L1.5 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
          </svg>
        </Box>
      )}
    </Box>
  </Box>
);

// Page wrapper component for consistent spacing and styling
export const IOSPageWrapper: React.FC<{
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
}> = ({ children, title, subtitle, action }) => {
  return (
    <Container size="xl" p={0}>
      {(title || subtitle || action) && (
        <Group justify="space-between" mb="xl">
          <Box>
            {title && (
              <Text
                component="h1"
                size="xl"
                fw={700}
                mb={subtitle ? rem(4) : 0}
                style={{
                  fontSize: rem(34),
                  lineHeight: 1.2,
                  color: '#1c1c1e',
                }}
              >
                {title}
              </Text>
            )}
            {subtitle && (
              <Text
                size="lg"
                c="dimmed"
                style={{
                  fontSize: rem(17),
                  lineHeight: 1.3,
                  color: '#8e8e93',
                }}
              >
                {subtitle}
              </Text>
            )}
          </Box>
          {action && <Box>{action}</Box>}
        </Group>
      )}
      {children}
    </Container>
  );
};

export default IOSCard;
