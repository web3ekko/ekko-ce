import React from 'react';
import {
  Stack,
  Text,
  SimpleGrid,
  Card,
  Group,
  ThemeIcon,
  Box,
} from '@mantine/core';
import {
  IconWallet,
  IconArrowsRightLeft,
  IconChartBar,
  IconTrendingUp,
} from '@tabler/icons-react';
import { AlertType, AlertCategory, AlertTypeConfig } from '@/@types/alert';
import { alertTypeConfigs } from '@/configs/alertTypes.config';

interface AlertTypeSelectorProps {
  value?: string; // Format: "type-category"
  onChange: (value: string) => void;
}

// Icon mapping for dynamic icon rendering
const iconMap = {
  IconWallet: IconWallet,
  IconArrowsRightLeft: IconArrowsRightLeft,
  IconChartBar: IconChartBar,
  IconTrendingUp: IconTrendingUp,
};

const AlertTypeSelector: React.FC<AlertTypeSelectorProps> = ({ value, onChange }) => {
  const getIconComponent = (iconName: string) => {
    const IconComponent = iconMap[iconName as keyof typeof iconMap] || IconWallet;
    return <IconComponent size={24} />;
  };

  const handleCardClick = (config: AlertTypeConfig) => {
    const typeValue = `${config.type}-${config.category}`;
    onChange(typeValue);
  };

  return (
    <Stack gap="md">
      <Box>
        <Text size="lg" fw={600} mb="xs">
          Choose Alert Type
        </Text>
        <Text size="sm" c="dimmed">
          Select the type of blockchain activity you want to monitor
        </Text>
      </Box>
      
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
        {alertTypeConfigs.map((config) => {
          const typeValue = `${config.type}-${config.category}`;
          const isSelected = value === typeValue;
          
          return (
            <Card
              key={typeValue}
              withBorder
              padding="lg"
              radius="md"
              style={{
                cursor: 'pointer',
                border: isSelected 
                  ? `2px solid ${config.color}` 
                  : '1px solid #e9ecef',
                backgroundColor: isSelected ? `${config.color}08` : 'white',
                transition: 'all 0.2s ease'
              }}
              onClick={() => handleCardClick(config)}
            >
              <Group align="flex-start" gap="md">
                <ThemeIcon 
                  size="lg" 
                  color={config.color} 
                  variant={isSelected ? "filled" : "light"}
                  radius="md"
                >
                  {getIconComponent(config.icon)}
                </ThemeIcon>
                
                <Box style={{ flex: 1 }}>
                  <Text fw={600} size="md" mb="xs">
                    {config.name}
                  </Text>
                  <Text size="sm" c="dimmed" mb="md">
                    {config.description}
                  </Text>
                  
                  <Stack gap="xs">
                    <Text size="xs" fw={500} c="dimmed">
                      Examples:
                    </Text>
                    {config.examples.slice(0, 2).map((example, idx) => (
                      <Text key={idx} size="xs" c="dimmed" style={{ lineHeight: 1.4 }}>
                        • {example}
                      </Text>
                    ))}
                  </Stack>
                </Box>
              </Group>
            </Card>
          );
        })}
      </SimpleGrid>
      
      {value && (
        <Card withBorder padding="md" radius="md" bg="blue.0">
          <Group>
            <ThemeIcon size="sm" color="blue" variant="light">
              <IconChartBar size={16} />
            </ThemeIcon>
            <Text size="sm" fw={500}>
              Selected: {alertTypeConfigs.find(c => `${c.type}-${c.category}` === value)?.name}
            </Text>
          </Group>
        </Card>
      )}
    </Stack>
  );
};

export default AlertTypeSelector;
