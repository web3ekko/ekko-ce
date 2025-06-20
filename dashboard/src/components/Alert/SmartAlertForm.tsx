import React, { useState } from 'react';
import {
  Stack,
  TextInput,
  Textarea,
  Switch,
  Button,
  Group,
  Card,
  Text,
  Badge,
  SimpleGrid,
  Alert,
  Loader,
  Center,
} from '@mantine/core';
import { IconInfoCircle, IconSparkles, IconEdit } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { AlertService } from '@/services/alert/alert.service';

interface SmartFormValues {
  name: string;
  description: string;
  enabled: boolean;
}

interface InferredAlert {
  type: string;
  category: string;
  name: string;
  description: string;
  condition: {
    query: string;
    parameters: Record<string, any>;
    data_sources: string[];
    estimated_frequency: string;
  };
  schedule: {
    type: string;
    timezone: string;
  };
  enabled: boolean;
  confidence?: number;
}

interface SmartAlertFormProps {
  onCreateAlert: (alert: InferredAlert) => void;
  onSwitchToAdvanced: (alert?: InferredAlert) => void;
  wallets: any[];
}

const SmartAlertForm: React.FC<SmartAlertFormProps> = ({
  onCreateAlert,
  onSwitchToAdvanced,
  wallets
}) => {
  const [formValues, setFormValues] = useState<SmartFormValues>({
    name: '',
    description: '',
    enabled: true
  });
  
  const [inferring, setInferring] = useState(false);
  const [inferredAlert, setInferredAlert] = useState<InferredAlert | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInputChange = (field: keyof SmartFormValues, value: any) => {
    setFormValues(prev => ({ ...prev, [field]: value }));
    // Clear inferred alert when user changes input
    if (inferredAlert) {
      setInferredAlert(null);
    }
  };

  const handleInferParameters = async () => {
    if (!formValues.description.trim()) {
      notifications.show({
        title: 'Missing Description',
        message: 'Please describe what you want to monitor',
        color: 'orange'
      });
      return;
    }

    setInferring(true);
    setError(null);

    try {
      // Call the parameter inference API
      const inferredData = await AlertService.inferParameters({
        name: formValues.name || 'Smart Alert',
        description: formValues.description,
        enabled: formValues.enabled,
        user_context: {
          wallets: wallets.map(w => ({
            id: w.id,
            name: w.name,
            address: w.address,
            blockchain_symbol: w.blockchain_symbol
          })),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        }
      });

      setInferredAlert(inferredData);

    } catch (err: any) {
      console.error('Error inferring parameters:', err);
      setError(err.message || 'Failed to analyze your description. Please try again.');
      
      notifications.show({
        title: 'Analysis Failed',
        message: 'Could not understand your description. Try being more specific or use Advanced Mode.',
        color: 'red'
      });
    } finally {
      setInferring(false);
    }
  };

  const handleCreateAlert = () => {
    if (inferredAlert) {
      onCreateAlert(inferredAlert);
    }
  };

  const handleEditParameters = () => {
    if (inferredAlert) {
      onSwitchToAdvanced(inferredAlert);
    }
  };

  // Handle creating alert without inference (simple mode)
  const handleCreateSimpleAlert = async () => {
    if (!formValues.description.trim()) {
      notifications.show({
        title: 'Missing Description',
        message: 'Please describe what you want to monitor',
        color: 'orange'
      });
      return;
    }

    // Create a simple alert without AI inference
    const simpleAlert = {
      id: `simple-${Date.now()}`,
      user_id: 'default',
      name: formValues.name || 'Smart Alert',
      description: formValues.description,
      type: 'wallet', // Default type
      category: 'balance', // Default category
      condition: {
        query: formValues.description,
        parameters: {},
        data_sources: ['wallet_balances'],
        estimated_frequency: 'real-time'
      },
      schedule: {
        type: 'real-time',
        timezone: 'UTC'
      },
      enabled: formValues.enabled,
      created_at: new Date().toISOString()
    };

    onCreateAlert(simpleAlert);
  };

  return (
    <Stack gap="md">
      <Alert icon={<IconSparkles size={16} />} color="blue" variant="light">
        <Text size="sm">
          <strong>Smart Mode:</strong> Describe what you want to monitor in natural language, 
          and AI will configure the alert for you.
        </Text>
      </Alert>

      <TextInput
        label="Alert Name"
        placeholder="My AVAX Balance Alert"
        value={formValues.name}
        onChange={(e) => handleInputChange('name', e.currentTarget.value)}
        required
      />
      
      <Textarea
        label="Describe what you want to monitor"
        placeholder="Examples:&#10;• Alert me when my main wallet balance falls below 10 AVAX&#10;• Notify me when AVAX price goes above $50&#10;• Alert on any transaction over 5 AVAX in my Optimidm wallet&#10;• Tell me when Trader Joe APR drops below 15%"
        minRows={4}
        value={formValues.description}
        onChange={(e) => handleInputChange('description', e.currentTarget.value)}
        required
      />
      
      <Switch
        label="Enable immediately"
        checked={formValues.enabled}
        onChange={(e) => handleInputChange('enabled', e.currentTarget.checked)}
      />

      <Group justify="space-between" mt="md">
        <Button
          variant="subtle"
          onClick={() => onSwitchToAdvanced()}
          leftSection={<IconEdit size={16} />}
        >
          Advanced Mode
        </Button>

        <Group>
          <Button
            variant="light"
            onClick={handleInferParameters}
            loading={inferring}
            disabled={!formValues.description.trim()}
            leftSection={<IconSparkles size={16} />}
          >
            {inferring ? 'Analyzing...' : 'Preview Alert'}
          </Button>

          <Button
            onClick={handleCreateSimpleAlert}
            disabled={!formValues.description.trim()}
            loading={inferring}
          >
            Create Alert
          </Button>
        </Group>
      </Group>

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}

      {inferring && (
        <Card withBorder padding="md">
          <Center>
            <Stack align="center" gap="sm">
              <Loader size="sm" />
              <Text size="sm" c="dimmed">Analyzing your description...</Text>
            </Stack>
          </Center>
        </Card>
      )}

      {inferredAlert && <InferredParametersPreview 
        alert={inferredAlert} 
        onCreateAlert={handleCreateAlert}
        onEditParameters={handleEditParameters}
      />}
    </Stack>
  );
};

interface InferredParametersPreviewProps {
  alert: InferredAlert;
  onCreateAlert: () => void;
  onEditParameters: () => void;
}

const InferredParametersPreview: React.FC<InferredParametersPreviewProps> = ({
  alert,
  onCreateAlert,
  onEditParameters
}) => {
  return (
    <Card withBorder padding="md" bg="blue.0">
      <Stack gap="sm">
        <Group justify="space-between">
          <Text fw={600}>AI Inferred Parameters</Text>
          <Group gap="xs">
            <Badge color="blue" variant="light">Smart Mode</Badge>
            {alert.confidence && (
              <Badge color={alert.confidence > 0.8 ? 'green' : 'orange'} variant="light">
                {Math.round(alert.confidence * 100)}% confident
              </Badge>
            )}
          </Group>
        </Group>
        
        <SimpleGrid cols={2} spacing="xs">
          <Text size="sm"><strong>Type:</strong> {alert.type}</Text>
          <Text size="sm"><strong>Category:</strong> {alert.category}</Text>
          
          {alert.condition.parameters.wallet_name && (
            <Text size="sm"><strong>Wallet:</strong> {alert.condition.parameters.wallet_name}</Text>
          )}
          
          {alert.condition.parameters.threshold && (
            <Text size="sm"><strong>Threshold:</strong> {alert.condition.parameters.threshold}</Text>
          )}
          
          {alert.condition.parameters.asset && (
            <Text size="sm"><strong>Asset:</strong> {alert.condition.parameters.asset}</Text>
          )}
          
          {alert.condition.parameters.comparison && (
            <Text size="sm"><strong>Condition:</strong> {alert.condition.parameters.comparison}</Text>
          )}
        </SimpleGrid>
        
        <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
          <Text size="sm" style={{ fontFamily: 'monospace' }}>
            <strong>Generated Query:</strong> {alert.condition.query}
          </Text>
        </Alert>
        
        <Group justify="space-between" mt="md">
          <Button 
            variant="light" 
            onClick={onEditParameters}
            leftSection={<IconEdit size={16} />}
          >
            Edit Parameters
          </Button>
          <Button 
            onClick={onCreateAlert}
            leftSection={<IconSparkles size={16} />}
          >
            Create Alert
          </Button>
        </Group>
      </Stack>
    </Card>
  );
};

export default SmartAlertForm;
