import React from 'react';
import {
  Text,
  Group,
  Button,
  Stack,
  Center,
  Box,
  rem,
  ThemeIcon,
} from '@mantine/core';
import {
  IconArrowsRightLeft,
  IconRocket,
  IconBell,
  IconSettings,
  IconCode,
} from '@tabler/icons-react';
import { IOSCard, IOSPageWrapper } from '@/components/UI/IOSCard';

export default function Workflows() {
  return (
    <IOSPageWrapper
      title="Workflows"
      subtitle="Blockchain-based intent execution engine"
    >
      <Center style={{ minHeight: rem(400) }}>
        <IOSCard elevated style={{ maxWidth: rem(600), width: '100%' }}>
          <Stack align="center" gap="xl" p="xl">
            {/* Main Icon */}
            <ThemeIcon
              size={rem(80)}
              radius="xl"
              variant="light"
              color="blue"
              style={{
                backgroundColor: '#f2f2f7',
              }}
            >
              <IconArrowsRightLeft size={40} />
            </ThemeIcon>

            {/* Coming Soon Text */}
            <Stack align="center" gap="md">
              <Text size="xl" fw={700} ta="center">
                Workflows Coming Soon
              </Text>
              <Text size="md" c="dimmed" ta="center" style={{ maxWidth: rem(400) }}>
                We're building an advanced workflow engine for executing blockchain-based intents.
                Create automated responses to on-chain events, set up complex trading strategies,
                and orchestrate multi-step blockchain operations.
              </Text>
            </Stack>

            {/* Feature Preview */}
            <Stack gap="sm" style={{ width: '100%' }}>
              <Group>
                <ThemeIcon size="sm" radius="xl" variant="light" color="green">
                  <IconRocket size={12} />
                </ThemeIcon>
                <Text size="sm" c="dimmed">
                  Automated transaction execution
                </Text>
              </Group>

              <Group>
                <ThemeIcon size="sm" radius="xl" variant="light" color="orange">
                  <IconBell size={12} />
                </ThemeIcon>
                <Text size="sm" c="dimmed">
                  Smart alert-driven actions
                </Text>
              </Group>

              <Group>
                <ThemeIcon size="sm" radius="xl" variant="light" color="purple">
                  <IconSettings size={12} />
                </ThemeIcon>
                <Text size="sm" c="dimmed">
                  Complex multi-step workflows
                </Text>
              </Group>

              <Group>
                <ThemeIcon size="sm" radius="xl" variant="light" color="blue">
                  <IconCode size={12} />
                </ThemeIcon>
                <Text size="sm" c="dimmed">
                  Custom logic and conditions
                </Text>
              </Group>
            </Stack>

            {/* Call to Action */}
            <Group>
              <Button variant="light" disabled>
                Get Notified
              </Button>
              <Button variant="outline" disabled>
                Learn More
              </Button>
            </Group>

            <Text size="xs" c="dimmed" ta="center">
              Expected release: Q2 2025
            </Text>
          </Stack>
        </IOSCard>
      </Center>
    </IOSPageWrapper>
  );
}
