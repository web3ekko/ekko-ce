import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Title,
  Paper,
  Group,
  Button,
  Loader,
  Alert as MantineAlert,
  Text,
  TextInput,
  Select,
  Switch,
  Grid,
  Center as MantineCenter,
  Breadcrumbs,
  Anchor,
  Stack,
  Badge,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import {
  IconDeviceFloppy,
  IconArrowLeft,
  IconAlertCircle,
  IconPencil,
  IconX,
} from '@tabler/icons-react';
import { nodesApi, Node } from '@/services/api/ekko';

// Define a type for the form values to ensure type safety
interface NodeFormValues {
  name: string;
  network: string;
  subnet: string;
  http_url: string;
  websocket_url: string;
  type: string;
  vm: string;
  is_enabled: boolean;
}

const NodeDetailPage: React.FC = () => {
  console.log('[NodeDetailPage] Rendering component...');
  const { nodeId } = useParams<{ nodeId: string }>();
  console.log('[NodeDetailPage] nodeId from useParams:', nodeId);
  const navigate = useNavigate();

  const [node, setNode] = useState<Node | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Initialize the form *before* useEffect hooks that might use it
  const form = useForm<NodeFormValues>({
    initialValues: {
      name: '',
      network: '',
      subnet: '',
      http_url: '',
      websocket_url: 'wss://example.com', // Placeholder, now required
      type: 'API', // Default type
      vm: 'EVM', // Default VM, now required
      is_enabled: true,
    },
    validate: {
      name: (value) => (value.trim().length < 1 ? 'Node name is required' : null),
      network: (value) => (value.trim().length < 1 ? 'Network is required' : null),
      subnet: (value) => (value.trim().length < 1 ? 'Subnet/Chain is required' : null),
      http_url: (value) => {
        if (value.trim().length < 1) return 'HTTP URL is required';
        try {
          new URL(value);
          return null;
        } catch (_) {
          return 'Invalid URL format';
        }
      },
      websocket_url: (value) => {
        if (!value || value.trim().length < 1) return 'WebSocket URL is required';
        try {
          new URL(value);
          return null;
        } catch (_) {
          return 'Invalid URL format';
        }
      },
      type: (value) => (value.trim().length < 1 ? 'Node type is required' : null),
      vm: (value) => (value.trim().length < 1 ? 'VM type is required' : null),
    },
  });
  console.log('[NodeDetailPage] Form initialized.');

  // Effect for fetching node details
  useEffect(() => {
    console.log('[NodeDetailPage] useEffect (fetch data): Triggered. nodeId:', nodeId);
    if (nodeId) {
      const fetchNodeDetails = async () => {
        console.log('[NodeDetailPage] fetchNodeDetails: Called. setLoading(true).');
        setLoading(true);
        setError(null);
        try {
          const data = await nodesApi.getNode(nodeId);
          console.log('[NodeDetailPage] fetchNodeDetails: API success, data received:', data);
          setNode(data);
        } catch (err: any) {
          console.error('[NodeDetailPage] fetchNodeDetails: API error caught.', err);
          setError(`Failed to load node details: ${err.message || 'Please try again.'}`);
          setNode(null); // Ensure node is null on error
        } finally {
          console.log('[NodeDetailPage] fetchNodeDetails: setLoading(false).');
          setLoading(false);
        }
      };
      fetchNodeDetails();
    } else {
      console.warn('[NodeDetailPage] useEffect (fetch data): nodeId is missing.');
      setError('Node ID is missing from URL.');
      setLoading(false);
      setNode(null);
    }
  }, [nodeId]); // Only depends on nodeId

  // Effect for populating form when node data is available or changes
  useEffect(() => {
    console.log('[NodeDetailPage] useEffect (populate form): Triggered. Node:', node);
    if (node) {
      console.log(
        '[NodeDetailPage] useEffect (populate form): Node data exists, setting form values.'
      );
      form.setValues({
        name: node.name || '',
        network: node.network || '',
        subnet: node.subnet || '',
        http_url: node.http_url || '',
        websocket_url: node.websocket_url,
        type: node.type || 'API',
        vm: node.vm,
        is_enabled: node.is_enabled !== undefined ? node.is_enabled : true,
      });
    } else {
      console.log('[NodeDetailPage] useEffect (populate form): Node data is null, resetting form.');
      form.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node, form.setValues]); // Using form.setValues as it's more stable

  const handleSubmit = async (values: NodeFormValues) => {
    console.log('[NodeDetailPage] handleSubmit: Called with form values:', values);
    if (!nodeId || !node) {
      console.error('[NodeDetailPage] handleSubmit: nodeId or original node data is missing.');
      setError('Cannot update node: essential data missing.');
      return;
    }
    setIsSaving(true);
    setError(null);

    const updatedNodeData: Node = {
      ...node, // Spread existing node data to preserve fields not in the form (like id, status, created_at etc.)
      ...values, // Spread form values to update changed fields
    };
    console.log(
      '[NodeDetailPage] handleSubmit: Attempting to update with payload:',
      updatedNodeData
    );

    try {
      const result = await nodesApi.updateNode(updatedNodeData);
      console.log('[NodeDetailPage] handleSubmit: API success, result:', result);
      setNode(result); // Update local state with response from API
      form.setValues(result); // Re-sync form with potentially modified data from backend
      setIsEditing(false); // Exit editing mode on successful save
      notifications.show({
        title: 'Node Updated',
        message: `Node ${result.name} has been updated successfully.`,
        color: 'green',
      });
    } catch (err: any) {
      console.error('[NodeDetailPage] handleSubmit: API error caught.', err);
      const errorMessage =
        err.response?.data?.detail || err.message || 'Please check console for details.';
      setError(`Failed to update node: ${errorMessage}`);
      notifications.show({
        title: 'Update Failed',
        message: `Failed to update node: ${errorMessage}`,
        color: 'red',
      });
    } finally {
      console.log('[NodeDetailPage] handleSubmit: setIsSaving(false).');
      setIsSaving(false);
    }
  };

  const breadcrumbsItems = [
    { title: 'Ekko', href: '/ekko' },
    { title: 'Nodes', href: '/ekko/nodes' },
    { title: node ? node.name : nodeId || 'Detail', href: `/ekko/nodes/${nodeId}` },
  ].map((item, index) => (
    <Anchor
      component="button"
      onClick={() => navigate(item.href)}
      key={index}
      style={{ fontSize: 'var(--mantine-font-size-sm)' }}
    >
      {item.title}
    </Anchor>
  ));

  // --- Rendering Logic ---
  console.log(
    '[NodeDetailPage] Render: Evaluating conditions - loading:',
    loading,
    'error:',
    error,
    'node:',
    node
  );

  if (loading) {
    console.log('[NodeDetailPage] Render: Showing Loading state.');
    return (
      <MantineCenter style={{ height: 'calc(100vh - 120px)' }}>
        <Loader size="xl" />
      </MantineCenter>
    );
  }

  if (error && !node) {
    // Show full page error only if node data couldn't be loaded at all
    console.log('[NodeDetailPage] Render: Showing Critical Error state -', error);
    return (
      <Container fluid p="md">
        <Breadcrumbs mb="md">{breadcrumbsItems}</Breadcrumbs>
        <MantineCenter style={{ height: 'calc(100vh - 200px)' }}>
          <MantineAlert
            title="Error Loading Node"
            color="red"
            radius="md"
            icon={<IconAlertCircle />}
          >
            {error}
          </MantineAlert>
        </MantineCenter>
      </Container>
    );
  }

  if (!node) {
    console.log(
      '[NodeDetailPage] Render: Showing Node Not Found state (node is null and not loading/critical error).'
    );
    return (
      <Container fluid p="md">
        <Breadcrumbs mb="md">{breadcrumbsItems}</Breadcrumbs>
        <MantineCenter style={{ height: 'calc(100vh - 200px)' }}>
          <Text>Node not found. It may have been deleted or the ID is incorrect.</Text>
        </MantineCenter>
      </Container>
    );
  }

  // Define options for select inputs (can be moved to a config or fetched)
  const networkOptions = ['Avalanche', 'Ethereum', 'Polygon', 'BSC', 'Other'];
  const subnetOptions = ['Mainnet', 'Fuji Testnet', 'Goerli', 'Sepolia', 'Custom', 'Other'];
  const typeOptions = ['API', 'Validator', 'Archive', 'Full', 'Other'];
  const vmOptions = ['EVM', 'Core', 'Custom', 'Other'];

  console.log(
    '[NodeDetailPage] Render: Showing Main Content with node:',
    node,
    'isEditing:',
    isEditing
  );
  return (
    <Container fluid p="md">
      <Breadcrumbs mb="lg">{breadcrumbsItems}</Breadcrumbs>
      <Paper shadow="sm" p="lg" withBorder>
        <Group justify="space-between" mb="xl">
          <Title order={2}>
            {isEditing ? `Edit Node: ${node.name}` : `Node Details: ${node.name}`}
          </Title>
          <Group>
            {!isEditing && (
              <Button
                leftSection={<IconPencil size={16} />}
                onClick={() => setIsEditing(true)}
                variant="outline"
              >
                Edit
              </Button>
            )}
          </Group>
        </Group>

        {error && isEditing && (
          <MantineAlert
            title="Update Error"
            color="red"
            radius="md"
            withCloseButton
            onClose={() => setError(null)}
            mb="md"
            icon={<IconAlertCircle />}
          >
            {error}
          </MantineAlert>
        )}

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Grid gutter="md">
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput
                label="Node Name"
                placeholder="Enter node name"
                required
                disabled={!isEditing}
                {...form.getInputProps('name')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Select
                label="Network"
                placeholder="Select network"
                data={networkOptions}
                required
                searchable
                disabled={!isEditing}
                {...form.getInputProps('network')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Select
                label="Subnet/Chain"
                placeholder="Select subnet or chain"
                data={subnetOptions}
                required
                searchable
                disabled={!isEditing}
                {...form.getInputProps('subnet')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput
                label="HTTP URL"
                placeholder="e.g., https://api.node.com"
                required
                type="url"
                disabled={!isEditing}
                {...form.getInputProps('http_url')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <TextInput
                label="WebSocket URL"
                placeholder="e.g., wss://ws.node.com"
                type="url"
                disabled={!isEditing}
                {...form.getInputProps('websocket_url')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Select
                label="Type"
                placeholder="Select node type"
                data={typeOptions}
                required
                searchable
                disabled={!isEditing}
                {...form.getInputProps('type')}
              />
            </Grid.Col>
            <Grid.Col span={{ base: 12, md: 6 }}>
              <Select
                label="VM"
                placeholder="Select VM type"
                data={vmOptions}
                searchable
                disabled={!isEditing}
                {...form.getInputProps('vm')}
              />
            </Grid.Col>
            <Grid.Col
              span={{ base: 12, md: 6 }}
              style={{ display: 'flex', alignItems: 'flex-end' }}
            >
              <Switch
                label="Enabled"
                description={
                  isEditing
                    ? "Toggle node's operational status"
                    : form.values.is_enabled
                      ? 'Node is currently operational'
                      : 'Node is currently disabled'
                }
                disabled={!isEditing}
                checked={form.values.is_enabled}
                onChange={(event) => form.setFieldValue('is_enabled', event.currentTarget.checked)}
                mt={isEditing ? 'sm' : undefined}
              />
            </Grid.Col>

            {!isEditing && (
              <>
                <Grid.Col span={{ base: 12 }}>
                  <Stack gap="xs" mt="md">
                    <Text c="dimmed" size="sm">
                      Additional Information
                    </Text>
                    <Group>
                      <Text fw={500} w={120}>
                        Status:
                      </Text>{' '}
                      <Badge
                        color={
                          node.status === 'Online'
                            ? 'green'
                            : node.status === 'Offline'
                              ? 'red'
                              : 'yellow'
                        }
                        variant="light"
                      >
                        {node.status || 'N/A'}
                      </Badge>
                    </Group>
                    <Group>
                      <Text fw={500} w={120}>
                        Created At:
                      </Text>{' '}
                      <Text>{new Date(node.created_at).toLocaleString()}</Text>
                    </Group>
                    <Group>
                      <Text fw={500} w={120}>
                        Last Updated:
                      </Text>{' '}
                      <Text>{new Date(node.updated_at).toLocaleString()}</Text>
                    </Group>
                  </Stack>
                </Grid.Col>
              </>
            )}
          </Grid>

          {isEditing && (
            <Group justify="flex-end" mt="xl">
              <Button
                variant="default"
                onClick={() => {
                  setIsEditing(false);
                  if (node)
                    form.setValues({
                      name: node.name || '',
                      network: node.network || '',
                      subnet: node.subnet || '',
                      http_url: node.http_url || '',
                      websocket_url: node.websocket_url,
                      type: node.type || 'API',
                      vm: node.vm,
                      is_enabled: node.is_enabled !== undefined ? node.is_enabled : true,
                    });
                  else form.reset();
                  setError(null);
                }}
                leftSection={<IconX size={16} />}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button type="submit" loading={isSaving} leftSection={<IconDeviceFloppy size={16} />}>
                Save Changes
              </Button>
            </Group>
          )}
        </form>
      </Paper>
    </Container>
  );
};

// Make sure to import notifications if you use it
import { notifications } from '@mantine/notifications';

export default NodeDetailPage;
