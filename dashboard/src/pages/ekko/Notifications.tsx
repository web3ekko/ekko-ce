import React, { useState } from 'react';
import {
  Text,
  Group,
  Button,
  Stack,
  Badge,
  ActionIcon,
  Menu,
  TextInput,
  Select,
  Box,
  rem,
  Divider,
  Center,
  Pagination,
} from '@mantine/core';
import {
  IconBell,
  IconMail,
  IconBrandDiscord,
  IconBrandTelegram,
  IconDots,
  IconTrash,
  IconEye,
  IconSearch,
  IconFilter,
  IconRefresh,
  IconCheck,
  IconX,
  IconClock,
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper, IOSSectionHeader } from '@/components/UI/IOSCard';

interface NotificationItem {
  id: string;
  title: string;
  message: string;
  type: 'email' | 'telegram' | 'discord';
  status: 'sent' | 'failed' | 'pending';
  timestamp: string;
  recipient: string;
  category: 'alert' | 'transaction' | 'system' | 'report';
}

export default function Notifications() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Mock notification data
  const [notifications] = useState<NotificationItem[]>([
    {
      id: '1',
      title: 'Price Alert Triggered',
      message: 'AVAX price has reached your target of $45.00',
      type: 'email',
      status: 'sent',
      timestamp: '2025-01-07T10:30:00Z',
      recipient: 'Personal Email (user@example.com)',
      category: 'alert',
    },
    {
      id: '2',
      title: 'Transaction Confirmed',
      message: 'Your transaction of 2.5 AVAX has been confirmed',
      type: 'telegram',
      status: 'sent',
      timestamp: '2025-01-07T09:15:00Z',
      recipient: 'Personal Telegram (@username)',
      category: 'transaction',
    },
    {
      id: '3',
      title: 'Low Balance Warning',
      message: 'Wallet balance below 1 AVAX threshold',
      type: 'discord',
      status: 'failed',
      timestamp: '2025-01-07T08:45:00Z',
      recipient: 'Team Discord (Webhook)',
      category: 'alert',
    },
    {
      id: '4',
      title: 'Weekly Portfolio Report',
      message: 'Your weekly portfolio summary is ready',
      type: 'email',
      status: 'pending',
      timestamp: '2025-01-07T08:00:00Z',
      recipient: 'Work Email (work@company.com)',
      category: 'report',
    },
    {
      id: '5',
      title: 'System Maintenance',
      message: 'Scheduled maintenance completed successfully',
      type: 'telegram',
      status: 'sent',
      timestamp: '2025-01-06T22:00:00Z',
      recipient: 'Alerts Channel (@alerts_bot)',
      category: 'system',
    },
    {
      id: '6',
      title: 'New Transaction Detected',
      message: 'Incoming transaction of 5.0 AVAX detected',
      type: 'email',
      status: 'sent',
      timestamp: '2025-01-06T18:30:00Z',
      recipient: 'Personal Email (user@example.com)',
      category: 'transaction',
    },
    {
      id: '7',
      title: 'Node Status Alert',
      message: 'Node avalanche-mainnet-1 is offline',
      type: 'discord',
      status: 'sent',
      timestamp: '2025-01-06T15:45:00Z',
      recipient: 'DevOps Discord (Webhook)',
      category: 'alert',
    },
  ]);

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <IconMail size={16} color="#007AFF" />;
      case 'telegram':
        return <IconBrandTelegram size={16} color="#0088cc" />;
      case 'discord':
        return <IconBrandDiscord size={16} color="#5865F2" />;
      default:
        return <IconBell size={16} />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'sent':
        return <Badge color="green" variant="light" leftSection={<IconCheck size={12} />}>Sent</Badge>;
      case 'failed':
        return <Badge color="red" variant="light" leftSection={<IconX size={12} />}>Failed</Badge>;
      case 'pending':
        return <Badge color="blue" variant="light" leftSection={<IconClock size={12} />}>Pending</Badge>;
      default:
        return <Badge color="gray" variant="light">Unknown</Badge>;
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'alert':
        return '#FF9500';
      case 'transaction':
        return '#34C759';
      case 'system':
        return '#007AFF';
      case 'report':
        return '#8E8E93';
      default:
        return '#8E8E93';
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate API call
    setTimeout(() => {
      setIsRefreshing(false);
    }, 1000);
  };

  const filteredNotifications = notifications.filter(notification => {
    const matchesSearch = notification.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         notification.message.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || notification.status === statusFilter;
    const matchesType = typeFilter === 'all' || notification.type === typeFilter;

    return matchesSearch && matchesStatus && matchesType;
  });

  const itemsPerPage = 10;
  const totalPages = Math.ceil(filteredNotifications.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedNotifications = filteredNotifications.slice(startIndex, startIndex + itemsPerPage);

  return (
    <IOSPageWrapper
      title="Notifications"
      subtitle="View your notification history and delivery status"
      action={
        <Button
          leftSection={<IconRefresh size={16} />}
          variant="light"
          loading={isRefreshing}
          onClick={handleRefresh}
        >
          Refresh
        </Button>
      }
    >
      <Stack gap="lg">
        {/* Filters */}
        <IOSCard>
          <Stack gap="md" p="md">
            <Group>
              <TextInput
                placeholder="Search notifications..."
                leftSection={<IconSearch size={16} />}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.currentTarget.value)}
                style={{ flex: 1 }}
              />

              <Select
                placeholder="Status"
                leftSection={<IconFilter size={16} />}
                value={statusFilter}
                onChange={(value) => setStatusFilter(value || 'all')}
                data={[
                  { value: 'all', label: 'All Status' },
                  { value: 'sent', label: 'Sent' },
                  { value: 'failed', label: 'Failed' },
                  { value: 'pending', label: 'Pending' },
                ]}
                style={{ width: rem(140) }}
              />

              <Select
                placeholder="Type"
                value={typeFilter}
                onChange={(value) => setTypeFilter(value || 'all')}
                data={[
                  { value: 'all', label: 'All Types' },
                  { value: 'email', label: 'Email' },
                  { value: 'telegram', label: 'Telegram' },
                  { value: 'discord', label: 'Discord' },
                ]}
                style={{ width: rem(140) }}
              />
            </Group>
          </Stack>
        </IOSCard>

        {/* Notifications List */}
        {paginatedNotifications.length === 0 ? (
          <IOSCard>
            <Center p="xl">
              <Stack align="center" gap="md">
                <IconBell size={48} color="#8E8E93" />
                <Text size="lg" fw={600} ta="center">No notifications found</Text>
                <Text size="sm" c="dimmed" ta="center">
                  {searchQuery || statusFilter !== 'all' || typeFilter !== 'all'
                    ? 'Try adjusting your filters'
                    : 'Notifications will appear here when they are sent'
                  }
                </Text>
              </Stack>
            </Center>
          </IOSCard>
        ) : (
          <Stack gap="sm">
            {paginatedNotifications.map((notification) => (
              <IOSCard key={notification.id}>
                <Group justify="space-between" p="md">
                  <Group gap="md" style={{ flex: 1 }}>
                    <Box
                      style={{
                        padding: rem(8),
                        borderRadius: rem(8),
                        backgroundColor: '#f2f2f7',
                      }}
                    >
                      {getTypeIcon(notification.type)}
                    </Box>

                    <Box style={{ flex: 1 }}>
                      <Group gap="xs" mb="xs">
                        <Text fw={600}>{notification.title}</Text>
                        <Badge
                          size="xs"
                          color={getCategoryColor(notification.category)}
                          variant="light"
                        >
                          {notification.category}
                        </Badge>
                        {getStatusBadge(notification.status)}
                      </Group>

                      <Text size="sm" c="dimmed" mb="xs">
                        {notification.message}
                      </Text>

                      <Group gap="md">
                        <Text size="xs" c="dimmed">
                          To: {notification.recipient}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {new Date(notification.timestamp).toLocaleString()}
                        </Text>
                      </Group>
                    </Box>
                  </Group>

                  <Menu position="bottom-end" withArrow>
                    <Menu.Target>
                      <ActionIcon variant="subtle" color="gray">
                        <IconDots size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item leftSection={<IconEye size={14} />}>
                        View Details
                      </Menu.Item>
                      {notification.status === 'failed' && (
                        <Menu.Item leftSection={<IconRefresh size={14} />}>
                          Retry
                        </Menu.Item>
                      )}
                      <Menu.Divider />
                      <Menu.Item leftSection={<IconTrash size={14} />} color="red">
                        Delete
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Group>
              </IOSCard>
            ))}
          </Stack>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <Center>
            <Pagination
              value={currentPage}
              onChange={setCurrentPage}
              total={totalPages}
              size="sm"
            />
          </Center>
        )}
      </Stack>
    </IOSPageWrapper>
  );
}
