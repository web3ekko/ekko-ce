import { useState } from 'react';
import { 
  AppShell, 
  Navbar, 
  Header, 
  Text, 
  MediaQuery, 
  Burger, 
  useMantineTheme,
  Grid,
  Card,
  Group,
  Badge,
  Stack,
  Title
} from '@mantine/core';
import { IconWallet, IconBell, IconRobot, IconChartBar } from '@tabler/icons-react';

// Mock data
const WALLETS = [
  { id: 1, name: 'Main Wallet', blockchain: 'AVAX', address: '0x1234...5678', balance: 2.345, status: 'active' },
  { id: 2, name: 'Trading Wallet', blockchain: 'ETH', address: '0x8765...4321', balance: 0.897, status: 'active' },
  { id: 3, name: 'Cold Storage', blockchain: 'BTC', address: 'bc1q...wxyz', balance: 0.123, status: 'active' },
  { id: 4, name: 'DeFi Wallet', blockchain: 'MATIC', address: '0xabcd...efgh', balance: 45.67, status: 'active' },
];

const ALERTS = [
  { id: 1, type: 'Balance', message: 'Main wallet balance below 3 AVAX', status: 'Open', priority: 'High' },
  { id: 2, type: 'Price', message: 'ETH price increased by 5% in last hour', status: 'Open', priority: 'Medium' },
];

export default function HomePage() {
  const theme = useMantineTheme();
  const [opened, setOpened] = useState(false);

  return (
    <AppShell
      styles={{
        main: {
          background: theme.colorScheme === 'dark' ? theme.colors.dark[8] : theme.colors.gray[0],
        },
      }}
      navbarOffsetBreakpoint="sm"
      navbar={
        <Navbar p="md" hiddenBreakpoint="sm" hidden={!opened} width={{ sm: 200, lg: 250 }}>
          <Navbar.Section>
            <Text size="xl" weight={700} color="blue">Ekko Dashboard</Text>
          </Navbar.Section>
          <Navbar.Section grow mt="lg">
            <Stack spacing="xs">
              <Text weight={500}><IconWallet size={18} style={{ marginRight: 8 }} />Wallets</Text>
              <Text weight={500}><IconBell size={18} style={{ marginRight: 8 }} />Alerts</Text>
              <Text weight={500}><IconRobot size={18} style={{ marginRight: 8 }} />Agents</Text>
              <Text weight={500}><IconChartBar size={18} style={{ marginRight: 8 }} />Analytics</Text>
            </Stack>
          </Navbar.Section>
        </Navbar>
      }
      header={
        <Header height={70} p="md">
          <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <MediaQuery largerThan="sm" styles={{ display: 'none' }}>
              <Burger
                opened={opened}
                onClick={() => setOpened((o) => !o)}
                size="sm"
                color={theme.colors.gray[6]}
                mr="xl"
              />
            </MediaQuery>
            <Text size="lg" weight={600}>Ekko Blockchain Monitor</Text>
          </div>
        </Header>
      }
    >
      <Title order={2} mb="md">Dashboard</Title>
      
      {/* Metrics */}
      <Grid mb="xl">
        <Grid.Col span={3}>
          <Card shadow="sm" p="lg">
            <Text size="lg" weight={700}>Total Balance</Text>
            <Text size="xl" weight={500} color="blue">$3.45K</Text>
          </Card>
        </Grid.Col>
        <Grid.Col span={3}>
          <Card shadow="sm" p="lg">
            <Text size="lg" weight={700}>Wallets</Text>
            <Text size="xl" weight={500} color="blue">{WALLETS.length}</Text>
          </Card>
        </Grid.Col>
        <Grid.Col span={3}>
          <Card shadow="sm" p="lg">
            <Text size="lg" weight={700}>Active Alerts</Text>
            <Text size="xl" weight={500} color="blue">{ALERTS.length}</Text>
          </Card>
        </Grid.Col>
        <Grid.Col span={3}>
          <Card shadow="sm" p="lg">
            <Text size="lg" weight={700}>AI Agents</Text>
            <Text size="xl" weight={500} color="blue">3</Text>
          </Card>
        </Grid.Col>
      </Grid>
      
      {/* Wallets */}
      <Title order={3} mb="md">Wallet Balances</Title>
      <Grid>
        {WALLETS.map(wallet => (
          <Grid.Col key={wallet.id} span={4}>
            <Card shadow="sm" p="lg">
              <Group position="apart" mb="xs">
                <Text weight={600}>{wallet.name}</Text>
                <Badge color={wallet.status === 'active' ? 'green' : 'red'}>
                  {wallet.status === 'active' ? 'Active' : 'Inactive'}
                </Badge>
              </Group>
              <Text size="sm" color="dimmed" mb="xs">{wallet.address}</Text>
              <Text>
                Balance: <Text component="span" weight={600}>{wallet.balance} {wallet.blockchain}</Text>
              </Text>
            </Card>
          </Grid.Col>
        ))}
      </Grid>

      {/* Alerts */}
      <Title order={3} mt="xl" mb="md">Recent Alerts</Title>
      <Stack>
        {ALERTS.map(alert => (
          <Card key={alert.id} shadow="sm" p="md">
            <Group position="apart">
              <Group>
                <Badge size="lg">{alert.type}</Badge>
                <Text>{alert.message}</Text>
              </Group>
              <Badge color={alert.priority === 'High' ? 'red' : alert.priority === 'Medium' ? 'orange' : 'blue'}>
                {alert.priority}
              </Badge>
            </Group>
          </Card>
        ))}
      </Stack>
    </AppShell>
  );
}
