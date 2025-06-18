import React from 'react';
import {
  Stack,
  Text,
  Select,
  NumberInput,
  TextInput,
  Alert,
  Box,
} from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';
import { AlertTypeConfig, AlertParameterConfig, AlertFormValues } from '@/@types/alert';
import { generateQueryFromTemplate } from '@/configs/alertTypes.config';

interface ParameterBuilderProps {
  config: AlertTypeConfig;
  values: AlertFormValues;
  onChange: (field: string, value: any) => void;
  wallets: any[]; // Wallet type from your existing code
}

const ParameterBuilder: React.FC<ParameterBuilderProps> = ({ 
  config, 
  values, 
  onChange, 
  wallets 
}) => {
  const renderParameter = (param: AlertParameterConfig) => {
    const value = (values.parameters as any)[param.name];
    
    switch (param.type) {
      case 'wallet_selector':
        return (
          <Select
            key={param.name}
            label={param.label}
            description={param.description}
            placeholder="Select wallet"
            required={param.required}
            data={[
              { value: '', label: 'None' },
              ...wallets.map(wallet => ({
                value: wallet.id,
                label: `${wallet.name || 'Wallet'} (${wallet.blockchain_symbol}) - ${wallet.address.substring(0, 6)}...${wallet.address.substring(wallet.address.length - 4)}`
              }))
            ]}
            value={value || ''}
            onChange={(val) => {
              onChange(`parameters.${param.name}`, val);
              // Also store wallet info for query generation
              const selectedWallet = wallets.find(w => w.id === val);
              if (selectedWallet) {
                onChange('parameters.wallet_name', selectedWallet.name || 'Wallet');
                onChange('parameters.wallet_address', selectedWallet.address);
                onChange('parameters.token_symbol', selectedWallet.blockchain_symbol);
              }
            }}
            clearable={!param.required}
          />
        );
        
      case 'number':
        return (
          <NumberInput
            key={param.name}
            label={param.label}
            description={param.description}
            placeholder={`Enter ${param.label.toLowerCase()}`}
            required={param.required}
            min={param.min}
            max={param.max}
            step={param.step}
            value={value || ''}
            onChange={(val) => onChange(`parameters.${param.name}`, val)}
          />
        );
        
      case 'select':
        return (
          <Select
            key={param.name}
            label={param.label}
            description={param.description}
            placeholder={`Select ${param.label.toLowerCase()}`}
            required={param.required}
            data={param.options || []}
            value={value || ''}
            onChange={(val) => onChange(`parameters.${param.name}`, val)}
            clearable={!param.required}
          />
        );
        
      case 'text':
        return (
          <TextInput
            key={param.name}
            label={param.label}
            description={param.description}
            placeholder={`Enter ${param.label.toLowerCase()}`}
            required={param.required}
            value={value || ''}
            onChange={(e) => onChange(`parameters.${param.name}`, e.currentTarget.value)}
          />
        );
        
      default:
        return null;
    }
  };

  // Generate preview query
  const generateQueryPreview = () => {
    try {
      const preview = generateQueryFromTemplate(config.queryTemplate, values.parameters);
      return preview || 'Configure parameters to see preview...';
    } catch (error) {
      return 'Configure parameters to see preview...';
    }
  };

  return (
    <Stack gap="md">
      <Box>
        <Text size="lg" fw={600} mb="xs">
          Configure Alert Parameters
        </Text>
        <Text size="sm" c="dimmed">
          Set the specific conditions for your {config.name.toLowerCase()}
        </Text>
      </Box>
      
      <Stack gap="md">
        {config.parameters.map((param) => renderParameter(param))}
      </Stack>
      
      {/* Real-time query preview */}
      <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
        <Text size="sm" fw={500} mb="xs">
          Alert Preview:
        </Text>
        <Text size="sm" style={{ fontFamily: 'monospace' }}>
          {generateQueryPreview()}
        </Text>
      </Alert>
      
      {/* Parameter validation info */}
      {config.parameters.some(p => p.required) && (
        <Alert color="orange" variant="light">
          <Text size="sm">
            <strong>Required fields:</strong> {config.parameters.filter(p => p.required).map(p => p.label).join(', ')}
          </Text>
        </Alert>
      )}
    </Stack>
  );
};

export default ParameterBuilder;
