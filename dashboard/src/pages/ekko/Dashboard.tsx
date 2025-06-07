import React, { useState, useEffect } from 'react';
import {
  Grid,
  Text,
  Group,
  Button,
  SimpleGrid,
  Stack,
  Center,
  Loader,
  Box,
  rem,
} from '@mantine/core';
import {
  IconWallet,
  IconBell,
  IconTrendingUp,
  IconActivity,
  IconChevronRight,
  IconPlus,
  IconRefresh,
  IconArrowUpRight,
  IconArrowDownLeft,
  IconClock,
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper, IOSSectionHeader } from '@/components/UI/IOSCard';
import { useAppSelector } from '@/store';
import { useNavigate } from 'react-router-dom';

// Mock data for demonstration
const mockStats = {
  totalWallets: 8,
  activeAlerts: 2,
  totalBalance: '$12,456.78',
  recentTransactions: 15,
};

const mockRecentActivity = [
  {
    id: '1',
    type: 'wallet',
    action: 'Created new wallet',
    target: 'ETH Mainnet Wallet',
    timestamp: '5 minutes ago',
    icon: <IconWallet size={16} color="#007AFF" />,
  },
  {
    id: '2',
    type: 'alert',
    action: 'Price alert triggered',
    target: 'ETH > $2000',
    timestamp: '12 minutes ago',
    icon: <IconBell size={16} color="#FF9500" />,
  },
  {
    id: '3',
    type: 'transaction',
    action: 'Received transaction',
    target: '2.5 ETH',
    timestamp: '1 hour ago',
    icon: <IconArrowDownLeft size={16} color="#34C759" />,
  },
  {
    id: '4',
    type: 'transaction',
    action: 'Sent transaction',
    target: '0.1 BTC',
    timestamp: '3 hours ago',
    icon: <IconArrowUpRight size={16} color="#FF3B30" />,
  },
];

// Stats card component
interface StatsCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon: React.ReactNode;
  onClick?: () => void;
}

const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  change,
  changeType = 'neutral',
  icon,
  onClick,
}) => {
  const changeColor = {
    positive: 'green',
    negative: 'red',
    neutral: 'gray',
  }[changeType];

  return (
    <IOSCard
      interactive={!!onClick}
      elevated
      onClick={onClick}
      p="lg"
    >
      <Group justify="space-between" mb="xs">
        <Box
          style={{
            padding: rem(8),
            borderRadius: rem(8),
            backgroundColor: '#f2f2f7',
          }}
        >
          {icon}
        </Box>
        {onClick && <IconChevronRight size={16} color="#8e8e93" />}
      </Group>

      <Text size="sm" c="dimmed" fw={500} tt="uppercase" mb={4}>
        {title}
      </Text>

      <Text size="xl" fw={700} mb={change ? 4 : 0}>
        {value}
      </Text>

      {change && (
        <Text size="sm" c={changeColor} fw={500}>
          {change}
        </Text>
      )}
    </IOSCard>
  );
};

// Activity item component
const ActivityItem: React.FC<{ activity: typeof mockRecentActivity[0] }> = ({ activity }) => {
  return (
    <Group gap="sm" p="sm">
      <Box
        style={{
          padding: rem(8),
          borderRadius: rem(8),
          backgroundColor: '#f2f2f7',
        }}
      >
        {activity.icon}
      </Box>

      <Box style={{ flex: 1 }}>
        <Text size="sm">
          <Text component="span" fw={500}>
            {activity.action}
          </Text>{' '}
          <Text component="span" fw={600}>
            {activity.target}
          </Text>
        </Text>
        <Text size="xs" c="dimmed">
          {activity.timestamp}
        </Text>
      </Box>
    </Group>
  );
};

export default function Dashboard() {
  const navigate = useNavigate();
  const username = useAppSelector((state) => state.auth.user?.email?.split('@')[0] || 'User');
  const [loading, setLoading] = useState(false);

  const handleRefresh = () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => {
      setLoading(false);
    }, 1000);
  };

  return (
    <IOSPageWrapper
      title="Dashboard"
      subtitle={`Welcome back, ${username}! Here's your portfolio overview.`}
      action={
        <Group>
          <Button
            variant="light"
            leftSection={<IconRefresh size={16} />}
            onClick={handleRefresh}
            loading={loading}
          >
            Refresh
          </Button>
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => navigate('/wallets')}
          >
            Add Wallet
          </Button>
        </Group>
      }
    >
      <Stack gap="xl">
        {/* Stats Grid */}
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
          <StatsCard
            title="Total Wallets"
            value={mockStats.totalWallets}
            change="+1 this week"
            changeType="positive"
            icon={<IconWallet size={20} color="#007AFF" />}
            onClick={() => navigate('/wallets')}
          />
          <StatsCard
            title="Active Alerts"
            value={mockStats.activeAlerts}
            change="1 new today"
            changeType="neutral"
            icon={<IconBell size={20} color="#FF9500" />}
            onClick={() => navigate('/alerts')}
          />
          <StatsCard
            title="Total Balance"
            value={mockStats.totalBalance}
            change="+5.2% today"
            changeType="positive"
            icon={<IconTrendingUp size={20} color="#34C759" />}
            onClick={() => navigate('/analytics')}
          />
          <StatsCard
            title="Recent Transactions"
            value={mockStats.recentTransactions}
            icon={<IconActivity size={20} color="#8e8e93" />}
            onClick={() => navigate('/transactions')}
          />
        </SimpleGrid>

        {/* Main Content Grid */}
        <Grid>
          {/* Recent Activity */}
          <Grid.Col span={{ base: 12, lg: 8 }}>
            <IOSCard>
              <IOSSectionHeader
                title="Recent Activity"
                subtitle="Your latest blockchain activities"
                action={
                  <Button
                    variant="light"
                    size="sm"
                    onClick={() => navigate('/transactions')}
                  >
                    View All
                  </Button>
                }
              />

              <Stack gap={0} p="md">
                {mockRecentActivity.map((activity, index) => (
                  <Box key={activity.id}>
                    <ActivityItem activity={activity} />
                    {index < mockRecentActivity.length - 1 && (
                      <Box
                        style={{
                          height: '1px',
                          backgroundColor: '#e5e5ea',
                          margin: `${rem(8)} ${rem(16)}`,
                        }}
                      />
                    )}
                  </Box>
                ))}
              </Stack>
            </IOSCard>
          </Grid.Col>

          {/* Quick Actions */}
          <Grid.Col span={{ base: 12, lg: 4 }}>
            <IOSCard>
              <IOSSectionHeader
                title="Quick Actions"
                subtitle="Common tasks"
              />

              <Stack gap="sm" p="md">
                <Button
                  variant="light"
                  fullWidth
                  leftSection={<IconWallet size={16} />}
                  onClick={() => navigate('/wallets')}
                >
                  Add New Wallet
                </Button>
                <Button
                  variant="light"
                  fullWidth
                  leftSection={<IconBell size={16} />}
                  onClick={() => navigate('/alerts')}
                >
                  Create Alert
                </Button>
                <Button
                  variant="light"
                  fullWidth
                  leftSection={<IconTrendingUp size={16} />}
                  onClick={() => navigate('/analytics')}
                >
                  View Analytics
                </Button>
                <Button
                  variant="light"
                  fullWidth
                  leftSection={<IconActivity size={16} />}
                  onClick={() => navigate('/transactions')}
                >
                  View Transactions
                </Button>
              </Stack>
            </IOSCard>
          </Grid.Col>
        </Grid>
      </Stack>
    </IOSPageWrapper>
  );
}
