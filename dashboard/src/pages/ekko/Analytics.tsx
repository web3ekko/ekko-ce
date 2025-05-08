import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Grid, 
  Group, 
  Button, 
  Select,
  SegmentedControl,
  RingProgress,
  Stack
} from '@mantine/core';
import { 
  IconChartBar, 
  IconChartLine, 
  IconChartPie, 
  IconRefresh,
  IconWallet
} from '@tabler/icons-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell
} from 'recharts';

// Mock data for charts
const PRICE_DATA = [
  { name: 'May 1', AVAX: 35.2, ETH: 3120, BTC: 62400 },
  { name: 'May 2', AVAX: 34.8, ETH: 3080, BTC: 61800 },
  { name: 'May 3', AVAX: 36.1, ETH: 3150, BTC: 63200 },
  { name: 'May 4', AVAX: 37.5, ETH: 3220, BTC: 64500 },
  { name: 'May 5', AVAX: 36.9, ETH: 3180, BTC: 63900 },
  { name: 'May 6', AVAX: 38.2, ETH: 3250, BTC: 65100 },
  { name: 'May 7', AVAX: 39.5, ETH: 3310, BTC: 66400 },
  { name: 'May 8', AVAX: 40.2, ETH: 3380, BTC: 67200 },
];

const TRANSACTION_DATA = [
  { name: 'May 1', count: 12 },
  { name: 'May 2', count: 19 },
  { name: 'May 3', count: 15 },
  { name: 'May 4', count: 21 },
  { name: 'May 5', count: 18 },
  { name: 'May 6', count: 24 },
  { name: 'May 7', count: 28 },
  { name: 'May 8', count: 22 },
];

const ASSET_DISTRIBUTION = [
  { name: 'AVAX', value: 45 },
  { name: 'ETH', value: 30 },
  { name: 'BTC', value: 15 },
  { name: 'MATIC', value: 10 },
];

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

export default function Analytics() {
  const [timeRange, setTimeRange] = useState('week');
  const [chartType, setChartType] = useState('price');
  const [selectedAsset, setSelectedAsset] = useState('AVAX');
  
  // Helper function to format currency values
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(value);
  };

  // Calculate total portfolio value
  const totalPortfolioValue = 12345.67;
  
  // Calculate 24h change
  const change24h = 3.45;
  
  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Analytics</Title>
          <Text c="dimmed" size="sm">Blockchain performance metrics and insights</Text>
        </div>
        <Group>
          <Select
            value={timeRange}
            onChange={(value) => setTimeRange(value || 'week')}
            data={[
              { value: 'day', label: '24 Hours' },
              { value: 'week', label: '7 Days' },
              { value: 'month', label: '30 Days' },
              { value: 'year', label: '1 Year' },
            ]}
            style={{ width: '120px' }}
          />
          <Button leftSection={<IconRefresh size={16} />} variant="light">Refresh</Button>
        </Group>
      </Group>
      
      {/* Summary Cards */}
      <Grid mb="md">
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <Card withBorder p="lg">
            <Group justify="space-between">
              <div>
                <Text size="xs" c="dimmed">Total Portfolio Value</Text>
                <Text fw={700} size="lg">{formatCurrency(totalPortfolioValue)}</Text>
              </div>
              <IconWallet size={30} color="#228be6" />
            </Group>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <Card withBorder p="lg">
            <Group justify="space-between">
              <div>
                <Text size="xs" c="dimmed">24h Change</Text>
                <Text fw={700} size="lg" c={change24h >= 0 ? 'green' : 'red'}>
                  {change24h >= 0 ? '+' : ''}{change24h}%
                </Text>
              </div>
              <IconChartLine size={30} color={change24h >= 0 ? '#40c057' : '#fa5252'} />
            </Group>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <Card withBorder p="lg">
            <Group justify="space-between">
              <div>
                <Text size="xs" c="dimmed">Total Transactions</Text>
                <Text fw={700} size="lg">159</Text>
              </div>
              <IconChartBar size={30} color="#be4bdb" />
            </Group>
          </Card>
        </Grid.Col>
        
        <Grid.Col span={{ base: 12, md: 6, lg: 3 }}>
          <Card withBorder p="lg">
            <Group justify="space-between">
              <div>
                <Text size="xs" c="dimmed">Active Wallets</Text>
                <Text fw={700} size="lg">4</Text>
              </div>
              <IconWallet size={30} color="#fd7e14" />
            </Group>
          </Card>
        </Grid.Col>
      </Grid>
      
      {/* Chart Controls */}
      <Group mb="md">
        <SegmentedControl
          value={chartType}
          onChange={setChartType}
          data={[
            { label: 'Price', value: 'price' },
            { label: 'Transactions', value: 'transactions' },
            { label: 'Asset Distribution', value: 'distribution' },
          ]}
        />
        
        {chartType === 'price' && (
          <Select
            value={selectedAsset}
            onChange={(value) => setSelectedAsset(value || 'AVAX')}
            data={[
              { value: 'AVAX', label: 'AVAX' },
              { value: 'ETH', label: 'ETH' },
              { value: 'BTC', label: 'BTC' },
            ]}
            style={{ width: '100px' }}
          />
        )}
      </Group>
      
      {/* Charts */}
      <Card withBorder p="lg" h={400}>
        {chartType === 'price' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={PRICE_DATA}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip formatter={(value) => [`$${value}`, selectedAsset]} />
              <Legend />
              <Line 
                type="monotone" 
                dataKey={selectedAsset} 
                stroke="#8884d8" 
                activeDot={{ r: 8 }} 
              />
            </LineChart>
          </ResponsiveContainer>
        )}
        
        {chartType === 'transactions' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={TRANSACTION_DATA}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" fill="#8884d8" name="Transaction Count" />
            </BarChart>
          </ResponsiveContainer>
        )}
        
        {chartType === 'distribution' && (
          <Group justify="center" align="center" h="100%">
            <Stack align="center">
              <Text fw={700} size="lg" mb="md">Asset Distribution</Text>
              <ResponsiveContainer width={300} height={300}>
                <PieChart>
                  <Pie
                    data={ASSET_DISTRIBUTION}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {ASSET_DISTRIBUTION.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => [`${value}%`, 'Allocation']} />
                </PieChart>
              </ResponsiveContainer>
            </Stack>
          </Group>
        )}
      </Card>
    </div>
  );
}
