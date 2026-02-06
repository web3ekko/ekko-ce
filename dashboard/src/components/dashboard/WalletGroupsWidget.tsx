/**
 * Wallet Groups Widget
 *
 * Dashboard widget showing active wallet groups
 */

import { Card, Stack, Group, Text, Badge, Button, Loader, Center } from '@mantine/core'
import { IconUsers, IconArrowRight } from '@tabler/icons-react'
import { useWalletStore } from '../../store/wallets'
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export function WalletGroupsWidget() {
    const { walletGroups, isLoading, loadWalletGroups } = useWalletStore()
    const navigate = useNavigate()

    useEffect(() => {
        loadWalletGroups()
    }, [loadWalletGroups])

    if (isLoading && walletGroups.length === 0) {
        return (
            <Card
                shadow="sm"
                padding="lg"
                radius="md"
                withBorder
                style={{
                    background: '#FFFFFF',
                    border: '1px solid #E6E9EE',
                }}
            >
                <Center h={150}>
                    <Loader size="sm" color="blue" />
                </Center>
            </Card>
        )
    }

    return (
        <Card
            shadow="sm"
            padding="lg"
            radius="md"
            withBorder
            style={{
                background: '#FFFFFF',
                border: '1px solid #E6E9EE',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
            }}
        >
            <Stack gap="md" h="100%">
                {/* Header */}
                <Group justify="space-between">
                    <Group gap="xs">
                        <IconUsers size={20} color="#2563EB" />
                        <Text fw={600} size="lg" c="#0F172A">
                            Wallet Groups
                        </Text>
                    </Group>
                    <Badge size="sm" variant="light" color="blue">
                        {walletGroups.length} active
                    </Badge>
                </Group>

                {/* Groups List */}
                {walletGroups.length > 0 ? (
                    <Stack gap="sm">
                        {walletGroups.slice(0, 3).map((group) => (
                            <Group
                                key={group.id}
                                justify="space-between"
                                p="xs"
                                style={{
                                    borderRadius: 8,
                                    background: '#F8FAFC',
                                    border: '1px solid #E2E8F0',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                }}
                                onClick={() => navigate(`/dashboard/wallets/groups/${group.id}`)}
                            >
                                <Stack gap={2} style={{ flex: 1 }}>
                                    <Text size="sm" fw={500} c="#0F172A" lineClamp={1}>
                                        {group.name}
                                    </Text>
                                    <Group gap={8}>
                                        <Text size="xs" c="#64748B">
                                            {group.member_count || 0} members
                                        </Text>
                                    </Group>
                                </Stack>
                            </Group>
                        ))
                        }
                        {
                            walletGroups.length > 3 && (
                                <Text size="xs" c="dimmed" ta="center">
                                    +{walletGroups.length - 3} more groups
                                </Text>
                            )
                        }
                    </Stack >
                ) : (
                    <Center py="md">
                        <Stack align="center" gap="xs">
                            <Text size="sm" c="dimmed" ta="center">
                                No wallet groups yet
                            </Text>
                            <Button
                                size="xs"
                                variant="light"
                                onClick={() => navigate('/dashboard/wallets/groups')}
                            >
                                Create Group
                            </Button>
                        </Stack>
                    </Center>
                )}

                {/* View All Button */}
                <Button
                    variant="subtle"
                    rightSection={<IconArrowRight size={14} />}
                    onClick={() => navigate('/dashboard/wallets/groups')}
                    fullWidth
                    mt="auto"
                >
                    View All Groups
                </Button>
            </Stack >
        </Card >
    )
}
