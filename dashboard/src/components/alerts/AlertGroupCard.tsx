/**
 * Alert Group Card Component
 *
 * Displays an alert group with subscription controls
 */

import { Card, Group, Text, Badge, Button, Stack, Avatar, Tooltip } from '@mantine/core'
import { IconBell, IconCheck, IconPlus } from '@tabler/icons-react'
import type { GenericGroup } from '../../services/groups-api'
import { getGroupCategory, getGroupTags } from '../../store/alertGroups'
import { useState } from 'react'

interface AlertGroupCardProps {
    group: GenericGroup
    isSubscribed?: boolean
    onSubscribe: (groupId: string) => Promise<void>
    onUnsubscribe: (groupId: string) => Promise<void>
    onViewDetails?: (group: GenericGroup) => void
}

export function AlertGroupCard({ group, isSubscribed = false, onSubscribe, onUnsubscribe, onViewDetails }: AlertGroupCardProps) {
    const [isLoading, setIsLoading] = useState(false)

    const handleSubscriptionToggle = async () => {
        setIsLoading(true)
        try {
            if (isSubscribed) {
                await onUnsubscribe(group.id)
            } else {
                await onSubscribe(group.id)
            }
        } finally {
            setIsLoading(false)
        }
    }

    const getCategoryColor = (category: string) => {
        const colors: Record<string, string> = {
            'DeFi': 'blue',
            'NFT': 'orange',
            'Security': 'red',
            'Network': 'teal',
            'Trading': 'blue',
        }
        return colors[category] || 'gray'
    }

    const category = getGroupCategory(group)
    const tags = getGroupTags(group)
    const ownerInitial = group.owner_email?.charAt(0).toUpperCase() || '?'

    return (
        <Card
            shadow="sm"
            padding="lg"
            radius="md"
            withBorder
            style={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                background: '#FFFFFF',
                border: '1px solid #E6E9EE',
                transition: 'all 0.2s var(--transition-premium)',
                cursor: onViewDetails ? 'pointer' : 'default',
            }}
            onClick={() => onViewDetails?.(group)}
            styles={{
                root: {
                    '&:hover': {
                        boxShadow: 'var(--shadow-lg)',
                        transform: 'translateY(-2px)',
                    }
                }
            }}
        >
            <Stack gap="md" style={{ flex: 1 }}>
                {/* Header */}
                <Group justify="space-between" align="flex-start">
                    <Stack gap={4} style={{ flex: 1 }}>
                        <Text fw={600} size="lg" c="#0F172A" lineClamp={1}>
                            {group.name}
                        </Text>
                        <Text size="sm" c="#64748B" lineClamp={2}>
                            {group.description}
                        </Text>
                    </Stack>
                    <Badge
                        color={getCategoryColor(category)}
                        variant="light"
                        size="sm"
                    >
                        {category}
                    </Badge>
                </Group>

                {/* Stats */}
                <Group gap="lg">
                    <Tooltip label="Number of alerts in this group">
                        <Group gap={6}>
                            <IconBell size={16} color="#64748B" />
                            <Text size="sm" c="#475569" fw={500}>
                                {group.member_count || 0} alerts
                            </Text>
                        </Group>
                    </Tooltip>
                </Group>

                {/* Tags */}
                {tags.length > 0 && (
                    <Group gap={6}>
                        {tags.slice(0, 3).map((tag) => (
                            <Badge
                                key={tag}
                                size="xs"
                                variant="outline"
                                color="gray"
                                style={{ textTransform: 'lowercase' }}
                            >
                                #{tag}
                            </Badge>
                        ))}
                        {tags.length > 3 && (
                            <Badge size="xs" variant="outline" color="gray">
                                +{tags.length - 3}
                            </Badge>
                        )}
                    </Group>
                )}

                {/* Creator */}
                <Group gap="xs" mt="auto">
                    <Avatar size="xs" color="blue" radius="xl">
                        {ownerInitial}
                    </Avatar>
                    <Text size="xs" c="dimmed">
                        by {group.owner_email}
                    </Text>
                </Group>

                {/* Subscribe Button */}
                <Button
                    fullWidth
                    variant={isSubscribed ? 'light' : 'filled'}
                    color={isSubscribed ? 'gray' : 'blue'}
                    leftSection={isSubscribed ? <IconCheck size={16} /> : <IconPlus size={16} />}
                    onClick={(e) => {
                        e.stopPropagation()
                        handleSubscriptionToggle()
                    }}
                    loading={isLoading}
                    style={{
                        backgroundColor: isSubscribed ? '#F1F5F9' : '#2563EB',
                        color: isSubscribed ? '#475569' : '#FFFFFF',
                    }}
                >
                    {isSubscribed ? 'Subscribed' : 'Subscribe'}
                </Button>
            </Stack>
        </Card>
    )
}
