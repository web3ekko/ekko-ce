import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store';
import {
  fetchWallets,
  createWallet,
  deleteWallet,
  updateWallet,
  clearWalletsError,
} from '@/store/slices/walletsSlice';
import {
  Title,
  Text,
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
  Center,
} from '@mantine/core';
import { IOSCard, IOSPageWrapper } from '@/components/UI/IOSCard';
import { useForm } from '@mantine/form';
import { useNavigate } from 'react-router-dom';
import {
  IconSearch,
  IconPlus,
  IconRefresh,
  IconWallet,
  IconCheck,
  IconX,
  IconTrash,
  IconEdit,
  IconNetwork,
} from '@tabler/icons-react';

import type { Wallet } from '@/@types/wallet';

// Helper function to truncate wallet addresses
const truncateAddress = (address: string, startChars = 6, endChars = 4) => {
  if (!address) return '';
  if (address.length <= startChars + endChars) return address;
  const start = address.substring(0, startChars);
  const end = address.substring(address.length - endChars);
  return `${start}...${end}`;
};

const subnetOptionsByNetwork: Record<string, Array<{ value: string; label: string }>> = {
  ETH: [
    { value: 'mainnet', label: 'Ethereum Mainnet' },
    { value: 'sepolia', label: 'Sepolia Testnet' },
    { value: 'goerli', label: 'Goerli Testnet' },
  ],
  AVAX: [
    { value: 'mainnet_c', label: 'Avalanche Mainnet C-Chain' },
    { value: 'fuji_c', label: 'Fuji Testnet C-Chain' },
    { value: 'mainnet_x', label: 'Avalanche Mainnet X-Chain' },
    { value: 'fuji_x', label: 'Fuji Testnet X-Chain' },
  ],
  MATIC: [
    { value: 'mainnet', label: 'Polygon Mainnet' },
    { value: 'mumbai', label: 'Mumbai Testnet' },
  ],
  SOL: [
    { value: 'mainnet-beta', label: 'Solana Mainnet Beta' },
    { value: 'testnet', label: 'Solana Testnet' },
    { value: 'devnet', label: 'Solana Devnet' },
  ],
  BTC: [
    { value: 'mainnet', label: 'Bitcoin Mainnet' },
    { value: 'testnet', label: 'Bitcoin Testnet' },
  ],
  // Add more networks and their subnets as needed
};

// Wallet data will be fetched from the API

interface WalletFormValues {
  name: string;
  address: string;
  blockchain: string;
  subnet: string; // Added subnet
  description: string;
  isActive: boolean;
}

export default function Wallets() {
  const navigate = useNavigate();
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
      blockchain: 'ETH', // Default blockchain
      subnet: subnetOptionsByNetwork['ETH']?.[0]?.value || '', // Default to first subnet of default blockchain
      description: '',
      isActive: true,
    },
    validate: {
      name: (value: string) => (value.trim().length < 1 ? 'Wallet name is required' : null),
      subnet: (value: string) => (value.trim().length < 1 ? 'Subnet/Chain is required' : null),
      address: (value: string) => {
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
      subnet: values.subnet, // Added subnet
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
  const filteredWallets = wallets.filter(
    (wallet) =>
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
    <IOSPageWrapper
      title="Wallets"
      subtitle="Manage and monitor your blockchain wallets"
      action={
        <Button
          leftSection={<IconPlus size={16} />}
          variant="filled"
          onClick={() => setModalOpened(true)}
        >
          Add Wallet
        </Button>
      }
    >
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
              label="Blockchain/Network"
              placeholder="Select blockchain/network"
              data={[
                { value: 'ETH', label: 'Ethereum' },
                { value: 'AVAX', label: 'Avalanche' },
                { value: 'MATIC', label: 'Polygon' },
                { value: 'SOL', label: 'Solana' },
                { value: 'BTC', label: 'Bitcoin' },
                // Add more as needed
              ]}
              required
              {...form.getInputProps('blockchain')}
              onChange={(value) => {
                form.setFieldValue('blockchain', value || '');
                // Update subnet options and reset subnet if the new network doesn't have the current one
                const newSubnetOptions = subnetOptionsByNetwork[value || ''] || [];
                const currentSubnetIsValid = newSubnetOptions.some(
                  (opt) => opt.value === form.values.subnet
                );
                if (!currentSubnetIsValid) {
                  form.setFieldValue('subnet', newSubnetOptions[0]?.value || '');
                }
              }}
            />

            <TextInput
              label="Address"
              placeholder="e.g., 0x... or bc1..."
              required
              {...form.getInputProps('address')}
            />

            <Select
              label="Subnet/Chain"
              placeholder="Select subnet/chain"
              required
              data={subnetOptionsByNetwork[form.values.blockchain] || []}
              {...form.getInputProps('subnet')}
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
              <Button variant="light" onClick={() => setModalOpened(false)}>
                Cancel
              </Button>
              <Button type="submit" leftSection={<IconCheck size={16} />}>
                Add Wallet
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      {error && (
        <Alert color="red" title="Error" mb="md" onClose={() => dispatch(clearWalletsError())}>
          {error}
        </Alert>
      )}

      <IOSCard>
        <Group justify="space-between" mb="md" p="md">
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

        {loading && filteredWallets.length === 0 ? (
          <Center p="xl">
            <Loader />
          </Center>
        ) : !loading && filteredWallets.length === 0 ? (
          <Center mt="xl" mb="xl">
            <Stack align="center">
              <IconWallet size={48} stroke={1.5} color="gray" />
              <Text size="lg" fw={500}>
                No wallets found
              </Text>
              <Text size="sm" c="dimmed" ta="center">
                Create your first wallet by clicking the "Add Wallet" button above.
              </Text>
            </Stack>
          </Center>
        ) : (
          <Grid p="md">
            {paginatedWallets.map((wallet) => (
              <Grid.Col span={{ base: 12, md: 6, lg: 4 }} key={wallet.id}>
                <IOSCard
                  interactive
                  elevated
                  onClick={() => navigate(`/ekko/wallets/${wallet.id}`)}
                  p="md"
                >
                  <Group justify="space-between" mb="xs">
                    <Group>
                      <IconWallet size={20} color="#007AFF" />
                      <Text fw={700}>{wallet.name}</Text>
                    </Group>
                    <Badge
                      color={wallet.status === 'active' ? 'green' : 'red'}
                      style={{ cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleStatus(wallet);
                      }}
                    >
                      {wallet.status === 'active' ? 'Active' : 'Inactive'}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed" mb="md" title={wallet.address}>
                    {truncateAddress(wallet.address)}
                  </Text>
                  <Group justify="space-between">
                    <Text>Balance:</Text>
                    <Text fw={700}>
                      {wallet.balance} {wallet.blockchain_symbol}
                    </Text>
                  </Group>
                  <Group justify="flex-end" mt="md">
                    <ActionIcon
                      color="red"
                      variant="subtle"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteWallet(wallet.id);
                      }}
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                  </Group>
                </IOSCard>
              </Grid.Col>
            ))}
          </Grid>
        )}

        {filteredWallets.length > parseInt(pageSize) && (
          <Group justify="center" mt="xl" p="md">
            <Pagination value={activePage} onChange={setActivePage} total={totalPages} />
          </Group>
        )}
      </IOSCard>
    </IOSPageWrapper>
  );
}
