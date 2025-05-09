import React from "react";
import { 
  Grid, 
  Card, 
  Text, 
  Group, 
  RingProgress, 
  Table, 
  Badge, 
  Title, 
  Paper,
  SimpleGrid,
  useMantineTheme
} from "@mantine/core";
import { 
  IconArrowUpRight, 
  IconArrowDownRight, 
  IconWallet, 
  IconAlertCircle, 
  IconCoin, 
  IconGauge
} from "@tabler/icons-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAppSelector } from "@/store";
import { useNavigate } from 'react-router-dom';

// Mock data for demonstration
const walletData = [
  { name: 'Jan', value: 12 },
  { name: 'Feb', value: 19 },
  { name: 'Mar', value: 15 },
  { name: 'Apr', value: 27 },
  { name: 'May', value: 32 },
  { name: 'Jun', value: 24 },
  { name: 'Jul', value: 38 },
];

const transactionData = [
  { name: '00:00', value: 20 },
  { name: '04:00', value: 25 },
  { name: '08:00', value: 35 },
  { name: '12:00', value: 45 },
  { name: '16:00', value: 60 },
  { name: '20:00', value: 40 },
  { name: '24:00', value: 30 },
];

const recentTransactions = [
  { hash: '0x1a2b...3c4d', type: 'Transfer', amount: '0.25 ETH', status: 'Confirmed', time: '5 min ago', from: '0xabc...123', to: '0xdef...456', chain: 'ETH' },
  { hash: '0x5e6f...7g8h', type: 'Swap', amount: '150 USDT', status: 'Pending', time: '12 min ago', from: '0x789...abc', to: '0xdef...789', chain: 'ETH' },
  { hash: '0x9i0j...1k2l', type: 'Deposit', amount: '1.5 AVAX', status: 'Confirmed', time: '25 min ago', from: '0xghi...jkl', to: '0xmno...pqr', chain: 'AVAX' },
  { hash: '0x3m4n...5o6p', type: 'Withdraw', amount: '0.1 BTC', status: 'Failed', time: '30 min ago', from: '0xstu...vwx', to: '0xyz...123', chain: 'BTC' },
  { hash: '0x7q8r...9s0t', type: 'Transfer', amount: '500 MATIC', status: 'Confirmed', time: '45 min ago', from: '0x456...789', to: '0xabc...def', chain: 'MATIC' },
];

const chainDistribution = [
  { chain: 'ETH', value: 45, color: '#4c6ef5' },
  { chain: 'BTC', value: 25, color: '#f59f00' },
  { chain: 'AVAX', value: 20, color: '#e03131' },
  { chain: 'MATIC', value: 10, color: '#9775fa' },
];

// Define styles as objects for table alignment
const tableHeaderStyle = {
  textAlign: 'left' as const,
  fontWeight: 600,
  fontSize: '0.85rem',
  textTransform: 'uppercase' as const,
  padding: '10px 8px',
};

const tableCellStyle = {
  padding: '8px',
  verticalAlign: 'middle' as const,
};

const viewAllLinkStyle = {
  cursor: 'pointer',
  transition: 'all 0.2s ease',
};

export default function Dashboard() {
  const theme = useMantineTheme();
  // No classes needed with inline styles
  const navigate = useNavigate();
  const username = useAppSelector((state) => state.auth.user?.email?.split('@')[0] || 'User');
  
  // Helper function to get badge color based on status
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Confirmed':
        return 'green';
      case 'Pending':
        return 'yellow';
      case 'Failed':
        return 'red';
      default:
        return 'gray';
    }
  };
  
  // Navigation handlers
  const goToTransactions = () => navigate('/transactions');
  const goToAlerts = () => navigate('/alerts');  

  return (
    <>
      <Group justify="space-between" mb={30}>
        <div>
          <Title order={2}>Dashboard</Title>
          <Text c="dimmed">Welcome back, {username}!</Text>
        </div>
        <Text fw={500} c="dimmed">Today: {new Date().toLocaleDateString()}</Text>
      </Group>

      {/* Stats Cards */}
      <SimpleGrid cols={4} spacing="md" mb={30}>
        <Card withBorder p="md" radius="md">
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Total Wallets
              </Text>
              <Text fw={700} size="xl">
                {walletData.length * 4}
              </Text>
            </div>
            <IconWallet size={30} color={theme.colors.blue[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="green" fw={700}>
              <IconArrowUpRight size={12} stroke={1.5} />
              +24%
            </Text>{' '}
            compared to previous month
          </Text>
        </Card>

        <Card withBorder p="md" radius="md">
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Active Alerts
              </Text>
              <Text fw={700} size="xl">
                12
              </Text>
            </div>
            <IconAlertCircle size={30} color={theme.colors.red[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="red" fw={700}>
              <IconArrowUpRight size={12} stroke={1.5} />
              +5
            </Text>{' '}
            new alerts in the last 24 hours
          </Text>
        </Card>

        <Card withBorder p="md" radius="md">
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Total Balance
              </Text>
              <Text fw={700} size="xl">
                $74.5K
              </Text>
            </div>
            <IconCoin size={30} color={theme.colors.yellow[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="green" fw={700}>
              <IconArrowUpRight size={12} stroke={1.5} />
              +18%
            </Text>{' '}
            compared to previous month
          </Text>
        </Card>

        <Card withBorder p="md" radius="md">
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Pending Orders
              </Text>
              <Text fw={700} size="xl">
                8
              </Text>
            </div>
            <IconGauge size={30} color={theme.colors.violet[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="red" fw={700}>
              <IconArrowDownRight size={12} stroke={1.5} />
              -3
            </Text>{' '}
            compared to yesterday
          </Text>
        </Card>
      </SimpleGrid>

      {/* Charts Section */}
      <Grid gutter="md" mb={30}>
        <Grid.Col span={8}>
          <Card withBorder p="md" radius="md" style={{ height: '100%' }}>
            <Title order={3} mb={20}>Transaction Volume</Title>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={transactionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line 
                  type="monotone" 
                  dataKey="value" 
                  stroke={theme.colors.blue[6]} 
                  strokeWidth={2}
                  dot={{ stroke: theme.colors.blue[6], strokeWidth: 2, r: 4 }}
                  activeDot={{ stroke: theme.colors.blue[7], strokeWidth: 2, r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={4}>
          <Card withBorder p="md" radius="md" style={{ height: '100%' }}>
            <Title order={3} mb={20}>Chain Distribution</Title>
            <Group justify="center" mt={30}>
              <RingProgress
                size={180}
                thickness={20}
                sections={chainDistribution.map(item => ({ value: item.value, color: item.color }))}
                label={
                  <Text size="xs" ta="center" px={10}>
                    Multi-chain
                    <Text size="xl" fw={700}>
                      4
                    </Text>
                    chains
                  </Text>
                }
              />
            </Group>
            <SimpleGrid cols={2} mt={30}>
              {chainDistribution.map((item, index) => (
                <Group key={index}>
                  <div style={{ width: 12, height: 12, backgroundColor: item.color, borderRadius: '50%' }} />
                  <div>
                    <Text size="xs">{item.chain}</Text>
                    <Text size="xs" fw={700}>{item.value}%</Text>
                  </div>
                </Group>
              ))}
            </SimpleGrid>
          </Card>
        </Grid.Col>
      </Grid>

      {/* Recent Transactions */}
      <div style={{ marginBottom: 30 }}>
        <Group justify="space-between" mb={10}>
          <Title order={4}>Recent Transactions</Title>
          <Badge 
            variant="light" 
            color="blue" 
            style={viewAllLinkStyle}
            onClick={goToTransactions}
          >
            VIEW ALL
          </Badge>
        </Group>
        <Card withBorder p="xs" radius="md">
          <Table striped highlightOnHover style={{ fontSize: '0.9rem' }}>
            <thead>
              <tr>
                <th style={tableHeaderStyle}>Hash</th>
                <th style={tableHeaderStyle}>Type</th>
                <th style={tableHeaderStyle}>Amount</th>
                <th style={tableHeaderStyle}>Status</th>
                <th style={tableHeaderStyle}>Time</th>
              </tr>
            </thead>
            <tbody>
              {recentTransactions.slice(0, 3).map((tx, index) => (
                <tr key={index} style={{ cursor: 'pointer' }} onClick={goToTransactions}>
                  <td style={tableCellStyle}>
                    <Group gap="xs">
                      <div style={{ width: 8, height: 8, backgroundColor: 
                        tx.chain === 'ETH' ? '#4c6ef5' : 
                        tx.chain === 'BTC' ? '#f59f00' : 
                        tx.chain === 'AVAX' ? '#e03131' : '#9775fa', 
                        borderRadius: '50%' }} />
                      <Text size="sm">{tx.hash}</Text>
                    </Group>
                  </td>
                  <td style={tableCellStyle}>
                    <Text size="sm">{tx.type}</Text>
                  </td>
                  <td style={tableCellStyle}>
                    <Text size="sm">{tx.amount}</Text>
                  </td>
                  <td style={tableCellStyle}>
                    <Badge size="sm" color={getStatusColor(tx.status)}>
                      {tx.status}
                    </Badge>
                  </td>
                  <td style={tableCellStyle}>
                    <Text size="sm" c="dimmed">{tx.time}</Text>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      </div>

      {/* Active Alerts */}
      <div>
        <Group justify="space-between" mb={10}>
          <Title order={4}>Active Alerts</Title>
          <Badge 
            variant="light" 
            color="blue" 
            style={viewAllLinkStyle}
            onClick={goToAlerts}
          >
            VIEW ALL
          </Badge>
        </Group>
        <Card withBorder p="xs" radius="md">
          <Table striped highlightOnHover style={{ fontSize: '0.9rem' }}>
            <thead>
              <tr>
                <th style={tableHeaderStyle}>Type</th>
                <th style={tableHeaderStyle}>Description</th>
                <th style={tableHeaderStyle}>Priority</th>
                <th style={tableHeaderStyle}>Time</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ cursor: 'pointer' }} onClick={goToAlerts}>
                <td style={tableCellStyle}>
                  <Group gap="xs">
                    <div style={{ width: 8, height: 8, backgroundColor: '#e03131', borderRadius: '50%' }} />
                    <Text size="sm">Price Alert</Text>
                  </Group>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm">ETH price dropped below $2,000</Text>
                </td>
                <td style={tableCellStyle}>
                  <Badge size="sm" color="red">High</Badge>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm" c="dimmed">15 minutes ago</Text>
                </td>
              </tr>
              <tr style={{ cursor: 'pointer' }} onClick={goToAlerts}>
                <td style={tableCellStyle}>
                  <Group gap="xs">
                    <div style={{ width: 8, height: 8, backgroundColor: '#f59f00', borderRadius: '50%' }} />
                    <Text size="sm">Wallet Activity</Text>
                  </Group>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm">Unusual withdrawal from Wallet #3</Text>
                </td>
                <td style={tableCellStyle}>
                  <Badge size="sm" color="yellow">Medium</Badge>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm" c="dimmed">32 minutes ago</Text>
                </td>
              </tr>
              <tr style={{ cursor: 'pointer' }} onClick={goToAlerts}>
                <td style={tableCellStyle}>
                  <Group gap="xs">
                    <div style={{ width: 8, height: 8, backgroundColor: '#e03131', borderRadius: '50%' }} />
                    <Text size="sm">Node Status</Text>
                  </Group>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm">AVAX node connection lost</Text>
                </td>
                <td style={tableCellStyle}>
                  <Badge size="sm" color="red">High</Badge>
                </td>
                <td style={tableCellStyle}>
                  <Text size="sm" c="dimmed">45 minutes ago</Text>
                </td>
              </tr>
            </tbody>
          </Table>
        </Card>
      </div>
    </>
  );
}
