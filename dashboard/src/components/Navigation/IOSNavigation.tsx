import React from 'react';
import {
  Box,
  Group,
  Text,
  UnstyledButton,
  Avatar,
  Badge,
  Stack,
  rem,
  Tooltip,
} from '@mantine/core';
import {
  IconHome,
  IconWallet,
  IconBell,
  IconUsers,
  IconSettings,
  IconActivity,
  IconServer,
  IconArrowsRightLeft,
} from '@tabler/icons-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppSelector } from '@/store';

interface NavItem {
  icon: React.ReactNode;
  label: string;
  path: string;
  badge?: number;
  color?: string;
}

const navItems: NavItem[] = [
  {
    icon: <IconHome size={24} />,
    label: 'Dashboard',
    path: '/dashboard',
    color: '#007AFF',
  },
  {
    icon: <IconWallet size={24} />,
    label: 'Wallets',
    path: '/wallets',
    color: '#34C759',
  },
  {
    icon: <IconBell size={24} />,
    label: 'Notifications',
    path: '/notifications',
    color: '#FF9500',
  },
  {
    icon: <IconArrowsRightLeft size={24} />,
    label: 'Workflows',
    path: '/workflows',
    color: '#8E8E93',
  },
  {
    icon: <IconActivity size={24} />,
    label: 'Transactions',
    path: '/transactions',
    color: '#FF3B30',
  },
  {
    icon: <IconServer size={24} />,
    label: 'Nodes',
    path: '/nodes',
    color: '#9775FA',
  },
];

interface NavItemProps {
  item: NavItem;
  isActive: boolean;
  onClick: () => void;
}

const NavItemComponent: React.FC<NavItemProps> = ({ item, isActive, onClick }) => {
  return (
    <Tooltip label={item.label} position="right" withArrow>
      <UnstyledButton
        onClick={onClick}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: rem(52),
          height: rem(52),
          borderRadius: rem(14),
          backgroundColor: isActive ? item.color : 'transparent',
          color: isActive ? '#ffffff' : item.color,
          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          position: 'relative',
          '&:hover': {
            backgroundColor: isActive ? item.color : `${item.color}15`,
            transform: 'scale(1.05)',
          },
          '&:active': {
            transform: 'scale(0.95)',
          },
        }}
      >
        {item.icon}
        {item.badge && (
          <Badge
            size="xs"
            variant="filled"
            color="red"
            style={{
              position: 'absolute',
              top: rem(-2),
              right: rem(-2),
              minWidth: rem(20),
              height: rem(20),
              padding: 0,
              fontSize: rem(11),
              fontWeight: 700,
              boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
            }}
          >
            {item.badge}
          </Badge>
        )}
      </UnstyledButton>
    </Tooltip>
  );
};

export const IOSNavigation: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAppSelector((state) => state.auth.user);

  const isActive = (path: string) => {
    return location.pathname.startsWith(path);
  };

  return (
    <Box
      style={{
        width: rem(88),
        height: '100vh',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(229, 229, 234, 0.6)',
        display: 'flex',
        flexDirection: 'column',
        padding: rem(18),
        position: 'fixed',
        left: 0,
        top: 0,
        zIndex: 100,
      }}
    >
      {/* Logo */}
      <Box
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: rem(36),
          padding: rem(8),
        }}
      >
        <Box
          style={{
            width: rem(36),
            height: rem(36),
            borderRadius: rem(10),
            backgroundColor: '#007AFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: rem(18),
            boxShadow: '0 2px 8px rgba(0, 122, 255, 0.3)',
          }}
        >
          E
        </Box>
      </Box>

      {/* Navigation Items */}
      <Stack gap="md" style={{ flex: 1 }}>
        {navItems.map((item) => (
          <NavItemComponent
            key={item.path}
            item={item}
            isActive={isActive(item.path)}
            onClick={() => navigate(item.path)}
          />
        ))}
      </Stack>

      {/* Bottom Section */}
      <Stack gap="md">
        {/* Settings */}
        <NavItemComponent
          item={{
            icon: <IconSettings size={24} />,
            label: 'Settings',
            path: '/settings',
            color: '#8E8E93',
          }}
          isActive={isActive('/settings')}
          onClick={() => navigate('/settings')}
        />

        {/* User Avatar */}
        <Box
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginTop: rem(16),
          }}
        >
          <Avatar
            size="md"
            radius="xl"
            style={{
              border: '2px solid rgba(229, 229, 234, 0.6)',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'scale(1.05)',
                borderColor: '#007AFF',
              },
            }}
            onClick={() => navigate('/profile')}
          >
            {user?.email?.charAt(0).toUpperCase() || 'U'}
          </Avatar>
        </Box>
      </Stack>
    </Box>
  );
};

// Mobile bottom navigation for smaller screens
export const IOSBottomNavigation: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    return location.pathname.startsWith(path);
  };

  const mobileNavItems = navItems.slice(0, 5); // Show first 5 items on mobile

  return (
    <Box
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        height: rem(80),
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        backdropFilter: 'blur(20px)',
        borderTop: '1px solid rgba(229, 229, 234, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-around',
        padding: `0 ${rem(16)}`,
        zIndex: 100,
        '@media (min-width: 768px)': {
          display: 'none',
        },
      }}
    >
      {mobileNavItems.map((item) => (
        <UnstyledButton
          key={item.path}
          onClick={() => navigate(item.path)}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: rem(4),
            padding: rem(8),
            borderRadius: rem(8),
            color: isActive(item.path) ? item.color : '#8E8E93',
            transition: 'all 0.2s ease',
            position: 'relative',
          }}
        >
          {item.icon}
          <Text size="xs" fw={500}>
            {item.label}
          </Text>
          {item.badge && (
            <Badge
              size="xs"
              variant="filled"
              color="red"
              style={{
                position: 'absolute',
                top: rem(4),
                right: rem(8),
                minWidth: rem(16),
                height: rem(16),
                padding: 0,
                fontSize: rem(9),
              }}
            >
              {item.badge}
            </Badge>
          )}
        </UnstyledButton>
      ))}
    </Box>
  );
};

export default IOSNavigation;
