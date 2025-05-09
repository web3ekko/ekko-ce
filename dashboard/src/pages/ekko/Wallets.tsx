import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Grid, 
  Badge, 
  Group, 
  Button, 
  TextInput,
  Pagination,
  Select,
  ActionIcon,
  Modal,
  Stack,
  Textarea,
  Switch,
  Divider
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconSearch, IconPlus, IconRefresh, IconWallet, IconCheck, IconX } from '@tabler/icons-react';

// This will be replaced with actual API data
const MOCK_WALLETS = [
  { id: '1', name: 'Main Wallet', address: '0x1234...5678', balance: 2.345, blockchain: 'AVAX', status: 'active' },
  { id: '2', name: 'Trading Wallet', address: '0x8765...4321', balance: 0.897, blockchain: 'ETH', status: 'active' },
  { id: '3', name: 'Cold Storage', address: 'bc1q...wxyz', balance: 0.123, blockchain: 'BTC', status: 'inactive' },
  { id: '4', name: 'DeFi Wallet', address: '0xabcd...efgh', balance: 45.67, blockchain: 'MATIC', status: 'active' },
];

interface WalletFormValues {
  name: string;
  address: string;
  blockchain: string;
  description: string;
  isActive: boolean;
}

export default function Wallets() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activePage, setActivePage] = useState(1);
  const [pageSize, setPageSize] = useState('10');
  const [modalOpened, setModalOpened] = useState(false);
  
  // Form for adding a new wallet
  const form = useForm<WalletFormValues>({
    initialValues: {
      name: '',
      address: '',
      blockchain: 'ETH',
      description: '',
      isActive: true,
    },
    validate: {
      name: (value) => (value.trim().length < 1 ? 'Wallet name is required' : null),
      address: (value) => {
        if (value.trim().length < 1) return 'Wallet address is required';
        // Basic validation for common blockchain address formats
        // This is simplified and should be enhanced for production
        const ethRegex = /^0x[a-fA-F0-9]{40}$/;
        const btcRegex = /^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$/;
        
        if (form.values.blockchain === 'ETH' || form.values.blockchain === 'AVAX' || form.values.blockchain === 'MATIC') {
          return ethRegex.test(value) ? null : 'Invalid Ethereum-style address';
        } else if (form.values.blockchain === 'BTC') {
          return btcRegex.test(value) ? null : 'Invalid Bitcoin address';
        }
        return null;
      },
    },
  });
  
  const handleSubmit = (values: WalletFormValues) => {
    // In a real app, this would call an API to add the wallet
    console.log('Adding new wallet:', values);
    // Close the modal after submission
    setModalOpened(false);
    // Reset form
    form.reset();
  };
  
  // Filter wallets based on search query
  const filteredWallets = MOCK_WALLETS.filter(wallet => 
    wallet.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
    wallet.address.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  // Calculate pagination
  const totalPages = Math.ceil(filteredWallets.length / parseInt(pageSize));
  const paginatedWallets = filteredWallets.slice(
    (activePage - 1) * parseInt(pageSize),
    activePage * parseInt(pageSize)
  );

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Wallets</Title>
          <Text c="dimmed" size="sm">Manage and monitor your blockchain wallets</Text>
        </div>
        <Button 
          leftSection={<IconPlus size={16} />} 
          variant="filled"
          onClick={() => setModalOpened(true)}
        >
          Add Wallet
        </Button>
        
        {/* Add Wallet Modal */}
        <Modal 
          opened={modalOpened} 
          onClose={() => setModalOpened(false)} 
          title="Add New Wallet"
          size="md"
        >
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <TextInput
                label="Wallet Name"
                placeholder="Main Wallet"
                required
                {...form.getInputProps('name')}
              />
              
              <Select
                label="Blockchain"
                placeholder="Select blockchain"
                data={[
                  { value: 'ETH', label: 'Ethereum (ETH)' },
                  { value: 'BTC', label: 'Bitcoin (BTC)' },
                  { value: 'AVAX', label: 'Avalanche (AVAX)' },
                  { value: 'MATIC', label: 'Polygon (MATIC)' },
                ]}
                required
                {...form.getInputProps('blockchain')}
              />
              
              <TextInput
                label="Wallet Address"
                placeholder="0x1234...5678"
                required
                {...form.getInputProps('address')}
              />
              
              <Textarea
                label="Description"
                placeholder="Optional description for this wallet"
                {...form.getInputProps('description')}
              />
              
              <Switch
                label="Active"
                checked={form.values.isActive}
                onChange={(event) => form.setFieldValue('isActive', event.currentTarget.checked)}
              />
              
              <Divider />
              
              <Group justify="flex-end">
                <Button variant="light" onClick={() => setModalOpened(false)}>Cancel</Button>
                <Button type="submit" leftSection={<IconCheck size={16} />}>Add Wallet</Button>
              </Group>
            </Stack>
          </form>
        </Modal>
      </Group>
      
      <Card withBorder mb="md">
        <Group justify="space-between" mb="md">
          <TextInput
            placeholder="Search wallets..."
            leftSection={<IconSearch size={16} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
            style={{ width: '300px' }}
          />
          <Group>
            <Select
              label="Items per page"
              value={pageSize}
              onChange={(value) => {
                setPageSize(value || '10');
                setActivePage(1);
              }}
              data={['5', '10', '20', '50']}
              style={{ width: '100px' }}
            />
            <ActionIcon variant="light" color="blue" size="lg" aria-label="Refresh">
              <IconRefresh size={18} />
            </ActionIcon>
          </Group>
        </Group>
        
        <Grid>
          {paginatedWallets.map(wallet => (
            <Grid.Col span={{ base: 12, md: 6, lg: 4 }} key={wallet.id}>
              <Card withBorder p="md" radius="md">
                <Group justify="space-between" mb="xs">
                  <Group>
                    <IconWallet size={20} />
                    <Text fw={700}>{wallet.name}</Text>
                  </Group>
                  <Badge color={wallet.status === 'active' ? 'green' : 'red'}>
                    {wallet.status === 'active' ? 'Active' : 'Inactive'}
                  </Badge>
                </Group>
                <Text size="sm" c="dimmed" mb="md">{wallet.address}</Text>
                <Group justify="space-between">
                  <Text>Balance:</Text>
                  <Text fw={700}>{wallet.balance} {wallet.blockchain}</Text>
                </Group>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
        
        {filteredWallets.length > parseInt(pageSize) && (
          <Group justify="center" mt="xl">
            <Pagination 
              value={activePage} 
              onChange={setActivePage} 
              total={totalPages} 
            />
          </Group>
        )}
      </Card>
    </div>
  );
}
