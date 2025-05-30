import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store';
import { fetchWallets, createWallet, deleteWallet, updateWallet, clearWalletsError } from '@/store/slices/walletsSlice';
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
  Divider,
  Loader,
  Alert,
  Center
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconSearch, IconPlus, IconRefresh, IconWallet, IconCheck, IconX, IconTrash, IconEdit } from '@tabler/icons-react';

import type { Wallet } from '@/@types/wallet';

// Wallet data will be fetched from the API

interface WalletFormValues {
  name: string;
  address: string;
  blockchain: string;
  description: string;
  isActive: boolean;
}

export default function Wallets() {
  const dispatch = useAppDispatch();
  const { wallets, loading, error } = useAppSelector((state) => state.wallets);
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
        const solanaRegex = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/;
        const avaxXRegex = /^X-[a-zA-Z0-9]{39}$/;
        
        switch (form.values.blockchain) {
          case 'ETH':
          case 'MATIC':
            return ethRegex.test(value) ? null : 'Invalid Ethereum-style address';
          case 'AVAX':
            // AVAX can use both Ethereum-style addresses (C-Chain) and X-Chain addresses
            return ethRegex.test(value) || avaxXRegex.test(value) ? null : 'Invalid AVAX address';
          case 'BTC':
            return btcRegex.test(value) ? null : 'Invalid Bitcoin address';
          case 'SOL':
            return solanaRegex.test(value) ? null : 'Invalid Solana address';
          default:
            return null;
        }
      },
    },
  });
  
  // Fetch wallets on component mount
  useEffect(() => {
    dispatch(fetchWallets());
  }, [dispatch]);

  const handleRefreshWallets = () => {
    dispatch(fetchWallets());
  };
  
  // Handle form submission for new wallet
  const handleSubmit = async (values: WalletFormValues) => {
    const walletPayload = {
      blockchain_symbol: values.blockchain,
      address: values.address,
      name: values.name,
      balance: 0, // Initial balance, or let backend decide
      status: values.isActive ? 'active' : 'inactive',
    };

    try {
      await dispatch(createWallet(walletPayload)).unwrap(); // unwrap to catch potential rejection
      setModalOpened(false);
      form.reset();
    } catch (err: any) {
      // Error is already handled by the slice and will be in the `error` state variable
      // You might want to show a notification here if needed
      console.error('Failed to create wallet:', err);
    }
  };
  
  // Handle wallet deletion
  const handleDeleteWallet = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this wallet?')) {
      try {
        await dispatch(deleteWallet(id)).unwrap();
      } catch (err) {
        console.error('Failed to delete wallet:', err);
      }
    }
  };
  
  // Toggle wallet status
  const handleToggleStatus = async (wallet: Wallet) => {
    const newStatus = wallet.status === 'active' ? 'inactive' : 'active';
    try {
      await dispatch(updateWallet({ id: wallet.id, data: { status: newStatus } })).unwrap();
    } catch (err) {
      console.error('Failed to update wallet status:', err);
    }
  };
  
  // Filter wallets based on search query
  const filteredWallets = wallets.filter(wallet => 
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
                  { value: 'SOL', label: 'Solana (SOL)' },
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
      
      {error && (
        <Alert color="red" title="Error" mb="md" onClose={() => dispatch(clearWalletsError())}>
          {error}
        </Alert>
      )}
      
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
            <ActionIcon 
              variant="light" 
              color="blue" 
              size="lg" 
              aria-label="Refresh"
              onClick={handleRefreshWallets}
            >
              <IconRefresh size={18} />
            </ActionIcon>
          </Group>
        </Group>
        
        {loading && wallets.length === 0 ? (
          <Center p="xl">
            <Loader />
          </Center>
        ) : (
          <Grid>
          {paginatedWallets.map(wallet => (
            <Grid.Col span={{ base: 12, md: 6, lg: 4 }} key={wallet.id}>
              <Card withBorder p="md" radius="md">
                <Group justify="space-between" mb="xs">
                  <Group>
                    <IconWallet size={20} />
                    <Text fw={700}>{wallet.name}</Text>
                  </Group>
                  <Badge 
                    color={wallet.status === 'active' ? 'green' : 'red'}
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleToggleStatus(wallet)}
                  >
                    {wallet.status === 'active' ? 'Active' : 'Inactive'}
                  </Badge>
                </Group>
                <Text size="sm" c="dimmed" mb="md">{wallet.address}</Text>
                <Group justify="space-between">
                  <Text>Balance:</Text>
                  <Text fw={700}>{wallet.balance} {wallet.blockchain_symbol}</Text>
                </Group>
                <Group justify="flex-end" mt="md">
                  <ActionIcon 
                    color="red" 
                    variant="subtle"
                    onClick={() => handleDeleteWallet(wallet.id)}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </Group>
              </Card>
            </Grid.Col>
          ))}
        </Grid>
        )}
        
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
