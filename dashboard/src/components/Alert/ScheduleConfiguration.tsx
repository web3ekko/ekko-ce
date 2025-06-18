import React from 'react';
import {
  Stack,
  Text,
  Radio,
  Select,
  TextInput,
  Alert,
  Group,
  ThemeIcon,
  Box,
} from '@mantine/core';
import { IconClock, IconInfoCircle, IconBolt } from '@tabler/icons-react';

interface ScheduleValue {
  type: 'real-time' | 'interval' | 'cron';
  interval_seconds?: number;
  cron_expression?: string;
  timezone: string;
}

interface ScheduleConfigurationProps {
  value: ScheduleValue;
  onChange: (value: ScheduleValue) => void;
}

const ScheduleConfiguration: React.FC<ScheduleConfigurationProps> = ({ value, onChange }) => {
  const handleTypeChange = (type: string) => {
    onChange({
      ...value,
      type: type as 'real-time' | 'interval' | 'cron'
    });
  };

  const handleIntervalChange = (seconds: string | null) => {
    onChange({
      ...value,
      interval_seconds: seconds ? parseInt(seconds) : undefined
    });
  };

  const handleCronChange = (expression: string) => {
    onChange({
      ...value,
      cron_expression: expression
    });
  };

  const getScheduleDescription = () => {
    switch (value.type) {
      case 'real-time':
        return 'Alert will be checked immediately when new blockchain data arrives. Best for time-sensitive alerts.';
      case 'interval':
        const interval = value.interval_seconds;
        if (!interval) return 'Select an interval to see description.';
        if (interval < 3600) return `Alert will be checked every ${interval / 60} minutes.`;
        if (interval < 86400) return `Alert will be checked every ${interval / 3600} hours.`;
        return `Alert will be checked every ${interval / 86400} days.`;
      case 'cron':
        return 'Use cron expressions for complex scheduling patterns (e.g., weekdays only, specific times).';
      default:
        return '';
    }
  };

  return (
    <Stack gap="md">
      <Box>
        <Text size="lg" fw={600} mb="xs">
          Alert Schedule
        </Text>
        <Text size="sm" c="dimmed">
          Choose when and how often to check this condition
        </Text>
      </Box>
      
      <Radio.Group
        value={value.type}
        onChange={handleTypeChange}
      >
        <Stack gap="md">
          <Radio 
            value="real-time" 
            label={
              <Group gap="xs">
                <ThemeIcon size="sm" color="green" variant="light">
                  <IconBolt size={14} />
                </ThemeIcon>
                <Text fw={500}>Real-time monitoring</Text>
              </Group>
            }
            description="Check condition immediately when new data arrives"
          />
          
          <Radio 
            value="interval" 
            label={
              <Group gap="xs">
                <ThemeIcon size="sm" color="blue" variant="light">
                  <IconClock size={14} />
                </ThemeIcon>
                <Text fw={500}>Periodic checks</Text>
              </Group>
            }
            description="Check condition at regular intervals"
          />
          
          <Radio 
            value="cron" 
            label={
              <Group gap="xs">
                <ThemeIcon size="sm" color="orange" variant="light">
                  <IconInfoCircle size={14} />
                </ThemeIcon>
                <Text fw={500}>Custom schedule</Text>
              </Group>
            }
            description="Use cron expression for complex scheduling"
          />
        </Stack>
      </Radio.Group>
      
      {value.type === 'interval' && (
        <Select
          label="Check Interval"
          placeholder="Select interval"
          description="How often to check the alert condition"
          data={[
            { value: '60', label: 'Every minute' },
            { value: '300', label: 'Every 5 minutes' },
            { value: '900', label: 'Every 15 minutes' },
            { value: '1800', label: 'Every 30 minutes' },
            { value: '3600', label: 'Every hour' },
            { value: '21600', label: 'Every 6 hours' },
            { value: '43200', label: 'Every 12 hours' },
            { value: '86400', label: 'Every day' }
          ]}
          value={value.interval_seconds?.toString() || ''}
          onChange={handleIntervalChange}
        />
      )}
      
      {value.type === 'cron' && (
        <Stack gap="xs">
          <TextInput
            label="Cron Expression"
            placeholder="0 */5 * * * *"
            description="Use standard cron syntax (second minute hour day month weekday)"
            value={value.cron_expression || ''}
            onChange={(e) => handleCronChange(e.currentTarget.value)}
          />
          
          <Alert color="blue" variant="light">
            <Text size="sm" fw={500} mb="xs">Common cron patterns:</Text>
            <Text size="xs" style={{ fontFamily: 'monospace' }}>
              • <strong>0 0 * * * *</strong> - Every hour<br/>
              • <strong>0 */15 * * * *</strong> - Every 15 minutes<br/>
              • <strong>0 0 9 * * *</strong> - Every day at 9 AM<br/>
              • <strong>0 0 9 * * 1-5</strong> - Weekdays at 9 AM
            </Text>
          </Alert>
        </Stack>
      )}
      
      {/* Schedule description */}
      <Alert icon={<IconInfoCircle size={16} />} color="blue" variant="light">
        <Text size="sm">
          {getScheduleDescription()}
        </Text>
      </Alert>
      
      {/* Timezone selector */}
      <Select
        label="Timezone"
        description="Timezone for scheduled alerts"
        data={[
          { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
          { value: 'America/New_York', label: 'Eastern Time (ET)' },
          { value: 'America/Chicago', label: 'Central Time (CT)' },
          { value: 'America/Denver', label: 'Mountain Time (MT)' },
          { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
          { value: 'Europe/London', label: 'London (GMT/BST)' },
          { value: 'Europe/Paris', label: 'Paris (CET/CEST)' },
          { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
          { value: 'Asia/Shanghai', label: 'Shanghai (CST)' }
        ]}
        value={value.timezone}
        onChange={(tz) => onChange({ ...value, timezone: tz || 'UTC' })}
        searchable
      />
    </Stack>
  );
};

export default ScheduleConfiguration;
