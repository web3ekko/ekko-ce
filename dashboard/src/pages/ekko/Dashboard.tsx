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
  useMantineTheme,
  Button,
  Progress,
  Divider,
  ActionIcon,
  Tooltip as MantineTooltip,
  Box,
  Select
} from "@mantine/core";
import { 
  IconArrowUpRight, 
  IconArrowDownRight, 
  IconWallet, 
  IconAlertCircle, 
  IconCoin, 
  IconGauge,
  IconExchange,
  IconBell,
  IconServer,
  IconSettings,
  IconChevronRight,
  IconArrowsRightLeft,
  IconEye,
  IconPlus
} from "@tabler/icons-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
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

const activeWallets = [
  { id: '1', name: 'Main ETH Wallet', address: '0x1a2b...3c4d', balance: 2.45, chain: 'ETH', color: '#4c6ef5', lastActivity: '2 hours ago' },
  { id: '2', name: 'Trading BTC', address: '0x5e6f...7g8h', balance: 0.15, chain: 'BTC', color: '#f59f00', lastActivity: '5 hours ago' },
  { id: '3', name: 'AVAX Staking', address: '0x9i0j...1k2l', balance: 45.75, chain: 'AVAX', color: '#e03131', lastActivity: '1 day ago' },
];

const activeAlerts = [
  { id: '1', type: 'Price', message: 'ETH price dropped below $2,000', priority: 'High', time: '15 minutes ago', color: '#e03131' },
  { id: '2', type: 'Wallet Activity', message: 'Unusual withdrawal from Wallet #3', priority: 'Medium', time: '32 minutes ago', color: '#f59f00' },
  { id: '3', type: 'Node Status', message: 'AVAX node connection lost', priority: 'High', time: '45 minutes ago', color: '#e03131' },
];

const activeWorkflows = [
  { id: '1', name: 'Price Alert to Transaction', status: 'Active', lastRun: '2 hours ago', triggers: 1, actions: 2 },
  { id: '2', name: 'Daily Portfolio Summary', status: 'Active', lastRun: '1 day ago', triggers: 1, actions: 1 },
];

const nodeStatus = [
  { id: '1', name: 'ETH Mainnet', status: 'Healthy', uptime: '99.8%', latency: '45ms' },
  { id: '2', name: 'AVAX C-Chain', status: 'Degraded', uptime: '95.2%', latency: '120ms' },
  { id: '3', name: 'BTC Node', status: 'Healthy', uptime: '99.9%', latency: '65ms' },
];

// Define styles as objects for table alignment
const tableHeaderStyle = {
  textAlign: 'left' as const,
  fontWeight: 600,
  fontSize: '0.75rem',
  textTransform: 'uppercase' as const,
  padding: '6px 4px',
};

const tableCellStyle = {
  padding: '4px',
  verticalAlign: 'middle' as const,
};

const viewAllLinkStyle = {
  cursor: 'pointer',
  transition: 'all 0.2s ease',
};

const sectionCardStyle = {
  height: 'auto',
  display: 'flex',
  flexDirection: 'column' as const,
};

const cardHeaderStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: '5px',
};

const COLORS = ['#4c6ef5', '#f59f00', '#e03131', '#9775fa', '#40c057', '#fd7e14'];

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'confirmed':
    case 'healthy':
    case 'active':
      return 'green';
    case 'pending':
    case 'degraded':
      return 'yellow';
    case 'failed':
    case 'down':
    case 'inactive':
      return 'red';
    default:
      return 'gray';
  }
};

const getPriorityColor = (priority: string) => {
  switch (priority.toLowerCase()) {
    case 'high':
      return 'red';
    case 'medium':
      return 'yellow';
    case 'low':
      return 'blue';
    default:
      return 'gray';
  }
};

export default function Dashboard() {
  const theme = useMantineTheme();
  // No classes needed with inline styles
  const navigate = useNavigate();
  const username = useAppSelector((state) => state.auth.user?.email?.split('@')[0] || 'User');
  
  // Helper functions
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Confirmed':
      case 'Active':
      case 'Healthy':
        return 'green';
      case 'Pending':
      case 'Issues':
        return 'yellow';
      case 'Failed':
      case 'Inactive':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'High':
        return 'red';
      case 'Medium':
        return 'yellow';
      case 'Low':
        return 'blue';
      default:
        return 'gray';
    }
  };

  // Navigation handlers
  const goToTransactions = () => navigate('/transactions');
  const goToAlerts = () => navigate('/alerts');
  const goToWallets = () => navigate('/wallets');
  const goToWorkflows = () => navigate('/workflows');
  const goToNodes = () => navigate('/nodes');
  const goToSettings = () => navigate('/settings');  

  return (
    <>
      <Group justify="space-between" mb={20}>
        <div>
          <Title order={2}>Dashboard</Title>
          <Text c="dimmed">Welcome back, {username}!</Text>
        </div>
        <Group>
          <Text fw={500} c="dimmed">Today: {new Date().toLocaleDateString()}</Text>
          <Button variant="light" leftSection={<IconSettings size={16} />} onClick={goToSettings}>Settings</Button>
        </Group>
      </Group>

      {/* Stats Cards */}
      <SimpleGrid cols={{ base: 1, sm: 2, md: 4 }} spacing="sm" mb="md">
        <Card withBorder p="sm" radius="md" component="a" href="#" onClick={goToWallets} style={{ cursor: 'pointer' }}>
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Total Wallets
              </Text>
              <Text fw={700} size="xl">
                {activeWallets.length}
              </Text>
            </div>
            <IconWallet size={30} color={theme.colors.blue[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="green" fw={700}>
              +{walletData[walletData.length - 1].value}%
            </Text>{" "}
            from last month
          </Text>
          <Button variant="subtle" rightSection={<IconChevronRight size={14} />} mt="xs" size="xs" fullWidth onClick={goToWallets}>View Wallets</Button>
        </Card>

        <Card withBorder p="sm" radius="md" component="a" href="#" onClick={goToAlerts} style={{ cursor: 'pointer' }}>
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Active Alerts
              </Text>
              <Text fw={700} size="xl">
                {activeAlerts.length}
              </Text>
            </div>
            <IconAlertCircle size={30} color={theme.colors.red[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="red" fw={700}>
              +2
            </Text>{" "}
            new alerts today
          </Text>
          <Button variant="subtle" rightSection={<IconChevronRight size={14} />} mt="xs" size="xs" fullWidth onClick={goToAlerts}>View Alerts</Button>
        </Card>

        <Card withBorder p="sm" radius="md" component="a" href="#" onClick={goToTransactions} style={{ cursor: 'pointer' }}>
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Total Balance
              </Text>
              <Text fw={700} size="xl">
                $12,456.78
              </Text>
            </div>
            <IconCoin size={30} color={theme.colors.yellow[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="green" fw={700}>
              +2.3%
            </Text>{" "}
            from yesterday
          </Text>
          <Button variant="subtle" rightSection={<IconChevronRight size={14} />} mt="xs" size="xs" fullWidth onClick={goToTransactions}>View Transactions</Button>
        </Card>

        <Card withBorder p="sm" radius="md" component="a" href="#" onClick={goToNodes} style={{ cursor: 'pointer' }}>
          <Group justify="space-between">
            <div>
              <Text c="dimmed" size="xs" tt="uppercase" fw={700}>
                Network Status
              </Text>
              <Text fw={700} size="xl">
                {nodeStatus.filter(node => node.status === 'Healthy').length}/{nodeStatus.length} Healthy
              </Text>
            </div>
            <IconServer size={30} color={theme.colors.green[6]} />
          </Group>
          <Text c="dimmed" size="sm" mt="md">
            <Text component="span" c="yellow" fw={700}>
              {nodeStatus.filter(node => node.status !== 'Healthy').length}
            </Text>{" "}
            {nodeStatus.filter(node => node.status !== 'Healthy').length === 1 ? 'node' : 'nodes'} with issues
          </Text>
          <Button variant="subtle" rightSection={<IconChevronRight size={14} />} mt="xs" size="xs" fullWidth onClick={goToNodes}>View Nodes</Button>
        </Card>
      </SimpleGrid>

      {/* Main Dashboard Content */}
      <Grid gutter="md">
        {/* Left Column */}
        <Grid.Col span={{ base: 12, md: 8 }}>
          {/* Portfolio Value Chart */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Portfolio Value</Title>
              <Group>
                <Select
                  size="xs"
                  defaultValue="7d"
                  data={[
                    { value: '24h', label: '24 Hours' },
                    { value: '7d', label: '7 Days' },
                    { value: '30d', label: '30 Days' },
                    { value: '90d', label: '90 Days' },
                  ]}
                />
              </Group>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={walletData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke={theme.colors.blue[6]} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>

          {/* Recent Transactions */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Recent Transactions</Title>
              <Group>
                <MantineTooltip label="View all transactions">
                  <ActionIcon variant="light" color="blue" onClick={goToTransactions}>
                    <IconEye size={16} />
                  </ActionIcon>
                </MantineTooltip>
              </Group>
            </div>
            <Table striped highlightOnHover style={{ fontSize: '0.8rem' }}>
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
                        <div style={{ width: 6, height: 6, backgroundColor: chainDistribution.find(c => c.chain === tx.chain)?.color || '#aaa', 
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
            <Button variant="light" fullWidth mt="xs" onClick={goToTransactions}>
              View All Transactions
            </Button>
          </Card>

          {/* Active Workflows */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Active Workflows</Title>
              <Group>
                <MantineTooltip label="Create new workflow">
                  <ActionIcon variant="light" color="blue" onClick={goToWorkflows}>
                    <IconPlus size={16} />
                  </ActionIcon>
                </MantineTooltip>
                <MantineTooltip label="View all workflows">
                  <ActionIcon variant="light" color="blue" onClick={goToWorkflows}>
                    <IconEye size={16} />
                  </ActionIcon>
                </MantineTooltip>
              </Group>
            </div>
            
            {activeWorkflows.length > 0 ? (
              <div>
                {activeWorkflows.map((workflow, index) => (
                  <Paper key={index} withBorder p="xs" radius="md" mb="xs" style={{ cursor: 'pointer' }} onClick={goToWorkflows}>
                    <Group justify="space-between">
                      <div>
                        <Group>
                          <IconArrowsRightLeft size={20} />
                          <div>
                            <Text fw={500}>{workflow.name}</Text>
                            <Text size="xs" c="dimmed">Last run: {workflow.lastRun}</Text>
                          </div>
                        </Group>
                      </div>
                      <Badge color={getStatusColor(workflow.status)}>{workflow.status}</Badge>
                    </Group>
                    <Group mt="xs" justify="space-between">
                      <Text size="xs">Triggers: {workflow.triggers}</Text>
                      <Text size="xs">Actions: {workflow.actions}</Text>
                    </Group>
                  </Paper>
                ))}
                <Button variant="light" fullWidth mt="xs" onClick={goToWorkflows}>
                  Manage Workflows
                </Button>
              </div>
            ) : (
              <div>
                <Text c="dimmed" ta="center" my="md">No active workflows</Text>
                <Button variant="light" fullWidth onClick={goToWorkflows}>
                  Create Workflow
                </Button>
              </div>
            )}
          </Card>
        </Grid.Col>

        {/* Right Column */}
        <Grid.Col span={{ base: 12, md: 4 }}>
          {/* Chain Distribution */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <Title order={5} mb="xs">Chain Distribution</Title>
            <Box mx="auto" style={{ width: '100%', height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chainDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {chainDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Box>
            <Divider my="sm" />
            <Group justify="space-between">
              {chainDistribution.map((item, index) => (
                <Group key={index} gap="xs">
                  <div style={{ width: 8, height: 8, backgroundColor: item.color, borderRadius: '50%' }} />
                  <Text size="xs">{item.chain}</Text>
                </Group>
              ))}
            </Group>
          </Card>

          {/* Active Wallets */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Active Wallets</Title>
              <MantineTooltip label="View all wallets">
                <ActionIcon variant="light" color="blue" onClick={goToWallets}>
                  <IconEye size={16} />
                </ActionIcon>
              </MantineTooltip>
            </div>
            {activeWallets.map((wallet, index) => (
              <Paper key={index} withBorder p="xs" radius="md" mb="xs" style={{ cursor: 'pointer' }} onClick={goToWallets}>
                <Group justify="space-between">
                  <Group>
                    <div style={{ width: 8, height: 8, backgroundColor: wallet.color, borderRadius: '50%' }} />
                    <div>
                      <Text fw={500}>{wallet.name}</Text>
                      <Text size="xs" c="dimmed">{wallet.address}</Text>
                    </div>
                  </Group>
                  <Text fw={700}>{wallet.balance} {wallet.chain}</Text>
                </Group>
                <Text size="xs" c="dimmed" mt="xs">Last activity: {wallet.lastActivity}</Text>
              </Paper>
            ))}
            <Button variant="light" fullWidth mt="xs" onClick={goToWallets}>
              Manage Wallets
            </Button>
          </Card>

          {/* Active Alerts */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Active Alerts</Title>
              <MantineTooltip label="View all alerts">
                <ActionIcon variant="light" color="blue" onClick={goToAlerts}>
                  <IconEye size={16} />
                </ActionIcon>
              </MantineTooltip>
            </div>
            {activeAlerts.map((alert, index) => (
              <Paper key={index} withBorder p="xs" radius="md" mb="xs" style={{ cursor: 'pointer' }} onClick={goToAlerts}>
                <Group justify="space-between">
                  <Group>
                    <div style={{ width: 8, height: 8, backgroundColor: alert.color, borderRadius: '50%' }} />
                    <div>
                      <Text fw={500}>{alert.type}</Text>
                      <Text size="xs">{alert.message}</Text>
                    </div>
                  </Group>
                  <Badge color={getPriorityColor(alert.priority)}>{alert.priority}</Badge>
                </Group>
                <Text size="xs" c="dimmed" mt="xs">{alert.time}</Text>
              </Paper>
            ))}
            <Button variant="light" fullWidth mt="xs" onClick={goToAlerts}>
              View All Alerts
            </Button>
          </Card>

          {/* Node Status */}
          <Card withBorder p="sm" radius="md" mb="xs" style={sectionCardStyle}>
            <div style={cardHeaderStyle}>
              <Title order={5}>Node Status</Title>
              <MantineTooltip label="View all nodes">
                <ActionIcon variant="light" color="blue" onClick={goToNodes}>
                  <IconEye size={16} />
                </ActionIcon>
              </MantineTooltip>
            </div>
            {nodeStatus.map((node, index) => (
              <Paper key={index} withBorder p="xs" radius="md" mb="xs" style={{ cursor: 'pointer' }} onClick={goToNodes}>
                <Group justify="space-between">
                  <Text fw={500}>{node.name}</Text>
                  <Badge color={getStatusColor(node.status)}>{node.status}</Badge>
                </Group>
                <Group justify="space-between" mt="xs">
                  <Text size="xs">Uptime: {node.uptime}</Text>
                  <Text size="xs">Latency: {node.latency}</Text>
                </Group>
              </Paper>
            ))}
            <Button variant="light" fullWidth mt="xs" onClick={goToNodes}>
              View All Nodes
            </Button>
          </Card>
        </Grid.Col>
      </Grid>
    </>
  );
}
