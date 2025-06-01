import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Title,
  Text,
  Paper,
  Group,
  Button,
  Loader,
  Stack,
  Badge,
  TextInput,
  Textarea,
  Switch,
  Grid,
  Divider,
  ActionIcon,
  Tooltip,
  Box,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { notifications } from '@mantine/notifications';
import { IconEdit, IconCheck, IconX, IconArrowLeft, IconWallet, IconNetwork, IconCurrencyEthereum, IconCurrencyBitcoin, IconCoin, IconQuestionMark, IconBox } from '@tabler/icons-react';

import { useAppDispatch, useAppSelector } from '@/store';
import { fetchWalletById, updateWallet } from '@/store/slices/walletsSlice';
import type { Wallet, WalletFormValues } from '@/@types/wallet';

// Helper to truncate address
const truncateAddress = (address: string, startChars = 6, endChars = 4) => {
  if (!address) return '';
  if (address.length <= startChars + endChars) return address;
  const start = address.substring(0, startChars);
  const end = address.substring(address.length - endChars);
  return `${start}...${end}`;
};

const getBlockchainIcon = (blockchain: string | undefined) => {
  switch (blockchain) {
    case 'Ethereum':
      return <IconCurrencyEthereum size={20} />;
    case 'Bitcoin':
      return <IconCurrencyBitcoin size={20} />;
    default:
      return <IconCoin size={20} />;
  }
};

export default function WalletDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const dispatch = useAppDispatch();

  const [localWallet, setLocalWallet] = useState<Wallet | null>(null); // Renamed to avoid conflict with Redux state
  const [pageLoading, setPageLoading] = useState(true); // Renamed to avoid conflict
  const [pageError, setPageError] = useState<string | null>(null); // Renamed to avoid conflict
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const { wallets: allWallets, loading: walletsGlobalLoading, error: walletsGlobalError } = useAppSelector((state) => state.wallets);
  // Attempt to find the wallet in the global state first
  const walletFromStore = allWallets.find(w => w.id === id);

  const form = useForm<Partial<WalletFormValues>>({
    initialValues: {
      name: '',
      description: '',
      isActive: true,
    },
    validate: {
      name: (value) => (value && value.trim().length > 0 ? null : 'Wallet name is required'),
    },
  });

  useEffect(() => {
    const loadWallet = async () => {
      if (!id) {
        setPageError('Wallet ID is missing.');
        setPageLoading(false);
        return;
      }
      setPageLoading(true);
      try {
        const fetchedWallet = await dispatch(fetchWalletById(id)).unwrap();
        setLocalWallet(fetchedWallet);
        form.setValues({
          name: fetchedWallet.name,
          description: fetchedWallet.description || '',
          isActive: fetchedWallet.isActive !== undefined ? fetchedWallet.isActive : true,
        });
        setPageError(null);
      } catch (err: any) {
        setPageError(err.message || 'Failed to load wallet details.');
        notifications.show({
          title: 'Error Loading Wallet',
          message: err.message || `Could not fetch details for wallet ${id}.`,
          color: 'red',
        });
      } finally {
        setPageLoading(false);
      }
    };

    if (id) {
      if (walletFromStore) {
        setLocalWallet(walletFromStore);
        form.setValues({
          name: walletFromStore.name,
          description: walletFromStore.description || '',
          isActive: walletFromStore.isActive !== undefined ? walletFromStore.isActive : true,
        });
        setPageLoading(false); // Already have it, no need to load page
        setPageError(null);
      } else {
        loadWallet();
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, dispatch, walletFromStore]); // Removed allWallets, form from deps

  const handleEditToggle = () => {
    if (localWallet && !editing) {
      form.setValues({
        name: localWallet.name,
        address: localWallet.address,
        blockchain: localWallet.blockchain_symbol,
        subnet: localWallet.subnet,
        description: localWallet.description || '',
        isActive: localWallet.isActive !== undefined ? localWallet.isActive : true,
      });
    }
    setEditing(!editing);
  };

  const handleSubmit = async (formValues: Partial<WalletFormValues>) => {
    if (!id || !localWallet) return;
    setSaving(true);
    try {
      // Ensure localWallet has all necessary fields. If not, this indicates an issue with fetch or initial state.
      // The backend PUT expects a full wallet representation.
      const completeWalletDataForUpdate: Wallet = {
        ...(localWallet as Wallet), // Cast to Wallet, assuming localWallet is populated correctly
        name: formValues.name!,
        description: formValues.description,
        isActive: formValues.isActive,
        // id is already part of localWallet and also handled by the service/URL parameter
      };

      // The updateWallet thunk expects Partial<Wallet>, but we send a complete object
      // to satisfy the backend's PUT requirement.
      const updatedWalletResult = await dispatch(updateWallet({ id, data: completeWalletDataForUpdate })).unwrap();
      setLocalWallet(updatedWalletResult); // Update local state with the response from API
      form.setValues({
        name: updatedWalletResult.name,
        description: updatedWalletResult.description || '',
        isActive: updatedWalletResult.isActive !== undefined ? updatedWalletResult.isActive : true,
        // Non-editable fields are not reset from formValues, they come from updatedWalletResult
        address: updatedWalletResult.address,
        blockchain: updatedWalletResult.blockchain_symbol,
        subnet: updatedWalletResult.subnet,
      });

      notifications.show({
        title: 'Success',
        message: 'Wallet updated successfully.',
        color: 'green',
      });
      setEditing(false);
    } catch (err: any) {
      notifications.show({
        title: 'Error updating wallet',
        message: err.message || 'An unknown error occurred.',
        color: 'red',
      });
    } finally {
      setSaving(false);
    }
  };

  if (pageLoading) return <Group justify="center" mt="xl"><Loader /></Group>;
  if (pageError) return <Text color="red" ta="center" mt="xl">{pageError}</Text>;
  if (!localWallet) return <Text ta="center" mt="xl">Wallet not found.</Text>;

  return (
    <Paper p="xl" withBorder>
      <Grid gutter="xl">
        <Grid.Col span={12}>
          <Group justify="space-between" mb="xl">
            <Tooltip label="Back to Wallets List">
              <ActionIcon onClick={() => navigate('/wallets')} variant="light" size="lg" title="Back to Wallets List">
                <IconArrowLeft size={20} />
              </ActionIcon>
            </Tooltip>
            <Title order={3} style={{ flexGrow: 1, textAlign: 'center' }}>
              {editing ? `Editing: ${localWallet.name}` : localWallet.name}
            </Title>
            {!editing ? (
              <Button leftSection={<IconEdit size={16} />} onClick={handleEditToggle} variant="outline">
                Edit Wallet
              </Button>
            ) : (
              <Box w={95} /> // Placeholder to keep alignment with edit button
            )}
          </Group>
        </Grid.Col>
        <Grid.Col span={12}>
          <Divider my="xl" />
        </Grid.Col>
        {editing ? (
          <Grid.Col span={12}>
            <form onSubmit={form.onSubmit(handleSubmit)}>
              <Stack gap="lg">
                <TextInput
                  label="Wallet Name"
                  placeholder="My Awesome Wallet"
                  required
                  {...form.getInputProps('name')}
                />
                <Textarea
                  label="Description"
                  placeholder="Optional description for this wallet"
                  minRows={3}
                  {...form.getInputProps('description')}
                />
                <Grid>
                  <Grid.Col span={{ base: 12, md: 6 }}>
                    <Text fw={500} size="sm">Address</Text>
                    <Text c="dimmed" style={{ wordBreak: 'break-all' }}>{localWallet.address}</Text>
                  </Grid.Col>
                  <Grid.Col span={{ base: 12, md: 6 }}>
                    <Text fw={500} size="sm">Blockchain</Text>
                    <Text><strong>Blockchain:</strong> {localWallet.blockchain_symbol}</Text>
                  </Grid.Col>
                  <Grid.Col span={{ base: 12, md: 6 }}>
                    <Text fw={500} size="sm">Subnet/Network</Text>
                    <Group><Text fw={700}>ID:</Text><Text size="sm" c="dimmed">{localWallet.id}</Text></Group>
                  </Grid.Col>
                  <Grid.Col span={{ base: 12, md: 6 }}>
                    <Switch
                      label="Active Status"
                      checked={form.values.isActive}
                      {...form.getInputProps('isActive', { type: 'checkbox' })}
                      mt="sm"
                    />
                  </Grid.Col>
                </Grid>
                <Group justify="flex-end" mt="lg">
                  <Button variant="default" onClick={handleEditToggle} disabled={saving}>
                    Cancel
                  </Button>
                  <Button type="submit" loading={saving} leftSection={<IconCheck size={16}/>}>
                    Save Changes
                  </Button>
                </Group>
              </Stack>
            </form>
          </Grid.Col>
        ) : (
          <Grid.Col span={12}>
            <Stack gap="md">
              <Grid gutter="xl">
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Name:</Text>
                  <Group><Text fw={700}>Name:</Text><Text>{localWallet.name}</Text></Group>
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Status:</Text>
                  <Group><Text fw={700}>Status:</Text><Badge color={localWallet.isActive ? 'green' : 'gray'}>{localWallet.isActive ? 'Active' : 'Inactive'}</Badge></Group>
                </Grid.Col>
                <Grid.Col span={12}>
                  <Text fw={500}>Address:</Text>
                  <Text style={{ wordBreak: 'break-all' }} title={localWallet.address}>{localWallet.address}</Text>
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Blockchain:</Text>
                  <Group><Text fw={700}>Blockchain:</Text><Text><strong>Blockchain:</strong> {localWallet.blockchain_symbol}</Text></Group>
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Subnet/Network:</Text>
                  <Group><Text fw={700}>Subnet/Network:</Text><Text c="dimmed">{localWallet.subnet}</Text></Group>
                </Grid.Col>
                {localWallet.description && (
                  <Grid.Col span={12}>
                    <Text fw={500}>Description:</Text>
                    <Paper p="xs" withBorder radius="sm" style={{backgroundColor: 'var(--mantine-color-gray-0)'}}>
                      <Text style={{ whiteSpace: 'pre-wrap' }}>{localWallet.description}</Text>
                    </Paper>
                  </Grid.Col>
                )}
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Created At:</Text>
                  <Group><Text fw={700}>Created:</Text><Text size="sm" c="dimmed">{localWallet.created_at ? new Date(localWallet.created_at).toLocaleString() : 'N/A'}</Text></Group>
                </Grid.Col>
                <Grid.Col span={{ base: 12, sm: 6 }}>
                  <Text fw={500}>Last Updated:</Text>
                  <Group><Text fw={700}>Last Updated:</Text><Text size="sm" c="dimmed">{localWallet.updated_at ? new Date(localWallet.updated_at).toLocaleString() : 'N/A'}</Text></Group>
                </Grid.Col>
              </Grid>
            </Stack>
          </Grid.Col>
        )}
      </Grid>
    </Paper>
  );
}
