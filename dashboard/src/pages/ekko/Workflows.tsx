import React, { useState } from 'react';
import { 
  Title, 
  Text, 
  Card, 
  Grid, 
  Group, 
  Button, 
  Badge,
  ActionIcon,
  Divider,
  Switch,
  Menu,
  Modal,
  TextInput,
  Textarea,
  Select,
  Stack
} from '@mantine/core';
import { 
  IconPlus, 
  IconArrowsRightLeft, 
  IconDotsVertical, 
  IconTrash,
  IconEdit,
  IconCopy,
  IconPlayerPlay,
  IconPlayerPause,
  IconCheck,
  IconAlertCircle,
  IconWallet,
  IconBell
} from '@tabler/icons-react';
import { useForm } from '@mantine/form';

// Mock data for workflows
const MOCK_WORKFLOWS = [
  { 
    id: '1', 
    name: 'Price Alert to Transaction', 
    description: 'Automatically execute a transaction when price reaches a threshold',
    status: 'active',
    triggers: ['Price Alert'],
    actions: ['Execute Transaction'],
    lastRun: '2025-05-08T14:30:00Z'
  },
  { 
    id: '2', 
    name: 'Low Balance Notification', 
    description: 'Send notification when wallet balance falls below threshold',
    status: 'active',
    triggers: ['Balance Alert'],
    actions: ['Send Notification'],
    lastRun: '2025-05-07T09:15:00Z'
  },
  { 
    id: '3', 
    name: 'Daily Portfolio Summary', 
    description: 'Generate and send daily portfolio summary report',
    status: 'inactive',
    triggers: ['Schedule (Daily)'],
    actions: ['Generate Report', 'Send Notification'],
    lastRun: '2025-05-06T18:00:00Z'
  },
  { 
    id: '4', 
    name: 'Security Alert Response', 
    description: 'Automatically secure wallet when security alert is triggered',
    status: 'active',
    triggers: ['Security Alert'],
    actions: ['Lock Wallet', 'Send Notification'],
    lastRun: '2025-05-05T22:45:00Z'
  },
];

interface WorkflowFormValues {
  name: string;
  description: string;
  trigger: string;
  action: string;
  isActive: boolean;
}

export default function Workflows() {
  const [modalOpened, setModalOpened] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState<string | null>(null);
  
  // Form for creating/editing a workflow
  const form = useForm<WorkflowFormValues>({
    initialValues: {
      name: '',
      description: '',
      trigger: 'price_alert',
      action: 'send_notification',
      isActive: true,
    },
    validate: {
      name: (value) => (value.trim().length < 1 ? 'Workflow name is required' : null),
    },
  });
  
  // Handle form submission
  const handleSubmit = (values: WorkflowFormValues) => {
    console.log('Saving workflow:', values);
    // Close the modal after submission
    setModalOpened(false);
    // Reset form
    form.reset();
    setEditingWorkflow(null);
  };
  
  // Open modal for editing a workflow
  const openEditModal = (id: string) => {
    const workflow = MOCK_WORKFLOWS.find(w => w.id === id);
    if (workflow) {
      form.setValues({
        name: workflow.name,
        description: workflow.description,
        trigger: workflow.triggers[0].toLowerCase().replace(' ', '_'),
        action: workflow.actions[0].toLowerCase().replace(' ', '_'),
        isActive: workflow.status === 'active',
      });
      setEditingWorkflow(id);
      setModalOpened(true);
    }
  };
  
  // Open modal for creating a new workflow
  const openCreateModal = () => {
    // Reset form to initial values
    form.setValues({
      name: '',
      description: '',
      trigger: 'price_alert',
      action: 'send_notification',
      isActive: true,
    });
    setEditingWorkflow(null);
    setModalOpened(true);
  };
  
  // Get trigger icon
  const getTriggerIcon = (trigger: string) => {
    switch (trigger) {
      case 'Price Alert': return <IconAlertCircle size={16} />;
      case 'Balance Alert': return <IconWallet size={16} />;
      case 'Security Alert': return <IconAlertCircle size={16} color="red" />;
      default: return <IconBell size={16} />;
    }
  };

  return (
    <div>
      <Group justify="space-between" mb="lg">
        <div>
          <Title order={2}>Workflows</Title>
          <Text c="dimmed" size="sm">Automate blockchain operations and responses</Text>
        </div>
        <Button 
          leftSection={<IconPlus size={16} />} 
          variant="filled"
          onClick={openCreateModal}
        >
          Create Workflow
        </Button>
        
        {/* Create/Edit Workflow Modal */}
        <Modal
          opened={modalOpened}
          onClose={() => {
            setModalOpened(false);
            setEditingWorkflow(null);
          }}
          title={editingWorkflow ? "Edit Workflow" : "Create New Workflow"}
          size="md"
        >
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <TextInput
                label="Workflow Name"
                placeholder="Price Alert to Transaction"
                required
                {...form.getInputProps('name')}
              />
              
              <Textarea
                label="Description"
                placeholder="Describe what this workflow does"
                {...form.getInputProps('description')}
              />
              
              <Select
                label="Trigger"
                description="What will trigger this workflow"
                data={[
                  { value: 'price_alert', label: 'Price Alert' },
                  { value: 'balance_alert', label: 'Balance Alert' },
                  { value: 'security_alert', label: 'Security Alert' },
                  { value: 'schedule', label: 'Schedule (Daily)' },
                ]}
                required
                {...form.getInputProps('trigger')}
              />
              
              <Select
                label="Action"
                description="What action to take when triggered"
                data={[
                  { value: 'send_notification', label: 'Send Notification' },
                  { value: 'execute_transaction', label: 'Execute Transaction' },
                  { value: 'generate_report', label: 'Generate Report' },
                  { value: 'lock_wallet', label: 'Lock Wallet' },
                ]}
                required
                {...form.getInputProps('action')}
              />
              
              <Switch
                label="Active"
                description="Enable or disable this workflow"
                checked={form.values.isActive}
                onChange={(event) => form.setFieldValue('isActive', event.currentTarget.checked)}
              />
              
              <Divider />
              
              <Group justify="flex-end">
                <Button 
                  variant="light" 
                  onClick={() => {
                    setModalOpened(false);
                    setEditingWorkflow(null);
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" leftSection={<IconCheck size={16} />}>
                  {editingWorkflow ? "Save Changes" : "Create Workflow"}
                </Button>
              </Group>
            </Stack>
          </form>
        </Modal>
      </Group>
      
      <Grid>
        {MOCK_WORKFLOWS.map((workflow) => (
          <Grid.Col span={{ base: 12, md: 6 }} key={workflow.id}>
            <Card withBorder p="md" radius="md">
              <Group justify="space-between" mb="xs">
                <Group>
                  <IconArrowsRightLeft size={20} />
                  <Text fw={700}>{workflow.name}</Text>
                </Group>
                <Group>
                  <Badge color={workflow.status === 'active' ? 'green' : 'gray'}>
                    {workflow.status === 'active' ? 'Active' : 'Inactive'}
                  </Badge>
                  <Menu position="bottom-end" withArrow>
                    <Menu.Target>
                      <ActionIcon variant="subtle">
                        <IconDotsVertical size={16} />
                      </ActionIcon>
                    </Menu.Target>
                    <Menu.Dropdown>
                      <Menu.Item 
                        leftSection={<IconEdit size={14} />}
                        onClick={() => openEditModal(workflow.id)}
                      >
                        Edit
                      </Menu.Item>
                      <Menu.Item 
                        leftSection={<IconCopy size={14} />}
                      >
                        Duplicate
                      </Menu.Item>
                      <Menu.Item 
                        leftSection={workflow.status === 'active' ? <IconPlayerPause size={14} /> : <IconPlayerPlay size={14} />}
                      >
                        {workflow.status === 'active' ? 'Disable' : 'Enable'}
                      </Menu.Item>
                      <Menu.Divider />
                      <Menu.Item 
                        leftSection={<IconTrash size={14} />}
                        color="red"
                      >
                        Delete
                      </Menu.Item>
                    </Menu.Dropdown>
                  </Menu>
                </Group>
              </Group>
              
              <Text size="sm" c="dimmed" mb="md">{workflow.description}</Text>
              
              <Divider mb="sm" />
              
              <Group mb="xs">
                <Text size="sm" fw={500}>Triggers:</Text>
                <Group gap={5}>
                  {workflow.triggers.map((trigger, index) => (
                    <Badge key={index} leftSection={getTriggerIcon(trigger)} size="sm">
                      {trigger}
                    </Badge>
                  ))}
                </Group>
              </Group>
              
              <Group mb="xs">
                <Text size="sm" fw={500}>Actions:</Text>
                <Group gap={5}>
                  {workflow.actions.map((action, index) => (
                    <Badge key={index} variant="outline" size="sm">
                      {action}
                    </Badge>
                  ))}
                </Group>
              </Group>
              
              <Text size="xs" c="dimmed" mt="md">
                Last run: {new Date(workflow.lastRun).toLocaleString()}
              </Text>
            </Card>
          </Grid.Col>
        ))}
      </Grid>
    </div>
  );
}
