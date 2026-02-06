/**
 * Alert Groups Widget
 *
 * Dashboard widget showing subscribed alert groups
 */

import { Card, Stack, Group, Text, Badge, Button, Loader, Center } from '@mantine/core'
import { IconBell, IconArrowRight, IconCheck } from '@tabler/icons-react'
import { useAlertGroupsStore, selectSubscribedGroups } from '../../store/alertGroups'
import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

export function AlertGroupsWidget() {
    const { groups, subscriptions, isLoading, loadGroups, loadSubscriptions } = useAlertGroupsStore()
    const navigate = useNavigate()

    // Compute subscribed groups from subscriptions
    const subscribedGroups = useMemo(() => {
        const subscribedIds = new Set(subscriptions.map((s) => s.alert_group))
        return groups.filter((g) => subscribedIds.has(g.id))
    }, [groups, subscriptions])

    useEffect(() => {
        loadGroups()
        loadSubscriptions()
    }, [loadGroups, loadSubscriptions])

    if (isLoading) {
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
                        <IconBell size={20} color="#2563EB" />
                        <Text fw={600} size="lg" c="#0F172A">
                            Alert Groups
                        </Text>
                    </Group>
                    <Badge size="sm" variant="light" color="blue">
                        {subscribedGroups.length} subscribed
                    </Badge>
                </Group>

                {/* Subscribed Groups */}
                {subscribedGroups.length > 0 ? (
                    <Stack gap="sm">
                        {subscribedGroups.slice(0, 3).map((group) => (
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
                                onClick={() => navigate(`/dashboard/alerts/groups/${group.id}`)}
                            >
                                <Stack gap={2} style={{ flex: 1 }}>
                                    <Text size="sm" fw={500} c="#0F172A" lineClamp={1}>
                                        {group.name}
                                    </Text>
                                    <Group gap={8}>
                                        <Text size="xs" c="#64748B">
                                            {group.member_count || 0} alerts
                                        </Text>
                                        <Text size="xs" c="#64748B">•</Text>
                                        <Badge size="xs" variant="light" color="green">
                                            <IconCheck size={10} style={{ marginRight: 2 }} />
                                            Active
                                        </Badge>
                                    </Group>
                                </Stack>
                            </Group>
                        ))}
                        {subscribedGroups.length > 3 && (
                            <Text size="xs" c="dimmed" ta="center">
                                +{subscribedGroups.length - 3} more groups
                            </Text>
                        )}
                    </Stack>
                ) : (
                    <Center py="md">
                        <Stack align="center" gap="xs">
                            <Text size="sm" c="dimmed" ta="center">
                                No subscribed groups yet
                            </Text>
                            <Button
                                size="xs"
                                variant="light"
                                onClick={() => navigate('/dashboard/alerts/groups')}
                            >
                                Browse Groups
                            </Button>
                        </Stack>
                    </Center>
                )}

                {/* View All Button */}
                <Button
                    variant="subtle"
                    rightSection={<IconArrowRight size={14} />}
                    onClick={() => navigate('/dashboard/alerts/groups')}
                    fullWidth
                    mt="auto"
                >
                    View All Groups
                </Button>
            </Stack>
        </Card >
    )
}
