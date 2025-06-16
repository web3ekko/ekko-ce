import React from 'react';
import {
  AppShell,
  Box,
  Container,
  Group,
  Text,
  ActionIcon,
  Avatar,
  Menu,
  UnstyledButton,
  rem,
  useMatches,
} from '@mantine/core';
import {
  IconBell,
  IconSearch,
  IconChevronDown,
  IconUser,
  IconSettings,
  IconLogout,
} from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '@/store';
import { signOutSuccess } from '@/store/slices/auth';
import { IOSNavigation, IOSBottomNavigation } from '../Navigation/IOSNavigation';

interface IOSLayoutProps {
  children: React.ReactNode;
}

export const IOSLayout: React.FC<IOSLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const user = useAppSelector((state) => state.auth.user);
  const isMobile = useMatches({ base: true, md: false });

  const handleSignOut = () => {
    dispatch(signOutSuccess());
    navigate('/auth/signin');
  };

  return (
    <AppShell
      navbar={{
        width: isMobile ? 0 : rem(88),
        breakpoint: 'md',
      }}
      header={{ height: rem(60) }}
      padding={0}
      style={{
        backgroundColor: '#f2f2f7',
      }}
    >
      {/* Desktop Navigation */}
      {!isMobile && (
        <AppShell.Navbar>
          <IOSNavigation />
        </AppShell.Navbar>
      )}

      {/* Header */}
      <AppShell.Header
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(229, 229, 234, 0.6)',
        }}
      >
        <Container size="xl" h="100%">
          <Group h="100%" justify="space-between" px={isMobile ? 'md' : 0}>
            {/* Left side - Search */}
            <Group>
              <ActionIcon
                variant="subtle"
                size="lg"
                radius="md"
                color="gray"
                style={{
                  backgroundColor: '#f2f2f7',
                }}
              >
                <IconSearch size={18} />
              </ActionIcon>
            </Group>

            {/* Right side - Notifications and User */}
            <Group gap="sm">
              {/* Notifications */}
              <ActionIcon
                variant="subtle"
                size="lg"
                radius="md"
                color="gray"
                style={{
                  backgroundColor: '#f2f2f7',
                  position: 'relative',
                }}
                onClick={() => navigate('/notifications')}
              >
                <IconBell size={18} />
                {/* Notification badge */}
                <Box
                  style={{
                    position: 'absolute',
                    top: rem(8),
                    right: rem(8),
                    width: rem(8),
                    height: rem(8),
                    borderRadius: '50%',
                    backgroundColor: '#FF3B30',
                  }}
                />
              </ActionIcon>

              {/* User Menu */}
              <Menu
                shadow="lg"
                width={200}
                radius="md"
                position="bottom-end"
                withArrow
              >
                <Menu.Target>
                  <UnstyledButton
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: rem(8),
                      padding: `${rem(4)} ${rem(8)}`,
                      borderRadius: rem(8),
                      transition: 'background-color 0.2s ease',
                      '&:hover': {
                        backgroundColor: '#f2f2f7',
                      },
                    }}
                  >
                    <Avatar size="sm" radius="xl">
                      {user?.email?.charAt(0).toUpperCase() || 'U'}
                    </Avatar>
                    <Text size="sm" fw={500} style={{ maxWidth: rem(100) }} truncate>
                      {user?.email?.split('@')[0] || 'User'}
                    </Text>
                    <IconChevronDown size={14} color="#8E8E93" />
                  </UnstyledButton>
                </Menu.Target>

                <Menu.Dropdown
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.9)',
                    backdropFilter: 'blur(20px)',
                    border: '1px solid rgba(229, 229, 234, 0.6)',
                  }}
                >
                  <Menu.Item
                    leftSection={<IconUser size={16} />}
                    onClick={() => navigate('/settings')}
                  >
                    Profile
                  </Menu.Item>
                  <Menu.Item
                    leftSection={<IconSettings size={16} />}
                    onClick={() => navigate('/settings')}
                  >
                    Settings
                  </Menu.Item>
                  <Menu.Divider />
                  <Menu.Item
                    leftSection={<IconLogout size={16} />}
                    color="red"
                    onClick={handleSignOut}
                  >
                    Sign Out
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
        </Container>
      </AppShell.Header>

      {/* Main Content */}
      <AppShell.Main
        style={{
          backgroundColor: '#f2f2f7',
          minHeight: '100vh',
          paddingBottom: isMobile ? rem(100) : rem(20), // Extra padding for mobile bottom nav
        }}
      >
        <Box
          style={{
            padding: rem(20),
            paddingLeft: isMobile ? rem(20) : rem(108), // Account for desktop sidebar
          }}
        >
          {children}
        </Box>
      </AppShell.Main>

      {/* Mobile Bottom Navigation */}
      {isMobile && <IOSBottomNavigation />}
    </AppShell>
  );
};

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

export default IOSLayout;
