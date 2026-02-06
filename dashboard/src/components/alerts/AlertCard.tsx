/**
 * Alert Card Component
 *
 * Compact alert display with selection support for bulk operations
 */

import { Card, Group, Text, Badge, Stack, Switch, ActionIcon, Menu, Checkbox, Box } from '@mantine/core'
import { IconBell, IconDots, IconEdit, IconTrash, IconCopy } from '@tabler/icons-react'
import type { Alert } from '../../store/simple-alerts'
import { useState } from 'react'
import { ChainLogo } from '../brand/ChainLogo'
import { getChainIdentity } from '../../utils/chain-identity'
import { AlertEventBadge } from './AlertEventBadge'

interface AlertCardProps {
    alert: Alert
    onToggle: (id: string) => void
    onEdit: (alert: Alert) => void
    onDelete: (id: string) => void
    onDuplicate: (alert: Alert) => void
    onClick?: (alert: Alert) => void
    selected?: boolean
    selectable?: boolean
    onSelect?: () => void
}

export function AlertCard({ alert, onToggle, onEdit, onDelete, onDuplicate, onClick, selected, selectable, onSelect }: AlertCardProps) {
    const [isToggling, setIsToggling] = useState(false)

    const handleToggle = async (e: React.MouseEvent) => {
        e.stopPropagation()
        setIsToggling(true)
        try {
            await onToggle(alert.id)
        } finally {
            setIsToggling(false)
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'active': return 'green'
            case 'paused': return 'yellow'
            case 'error': return 'red'
            default: return 'gray'
        }
    }

    const handleClick = () => {
        if (selectable && onSelect) {
            onSelect()
        } else if (onClick) {
            onClick(alert)
        }
    }

    return (
        <Card
            padding="xs"
            radius="sm"
            withBorder
            style={{
                background: selected ? '#EFF6FF' : '#FFFFFF',
                border: selected ? '1px solid #2563EB' : '1px solid #E6E9EE',
                cursor: selectable || onClick ? 'pointer' : 'default',
                transition: 'all 0.15s ease',
                height: '100%',
            }}
            onClick={handleClick}
            styles={{
                root: {
                    '&:hover': {
                        borderColor: selected ? '#2563EB' : '#94A3B8',
                        transform: 'translateY(-1px)',
                    }
                }
            }}
        >
            <Stack gap={6}>
                {/* Header - Compact */}
                <Group justify="space-between" align="flex-start">
                    <Group gap={6}>
                        {selectable && (
                            <Checkbox
                                checked={selected}
                                onChange={onSelect}
                                size="xs"
                                onClick={(e) => e.stopPropagation()}
                            />
                        )}
                        <Box
                            style={{
                                width: 20,
                                height: 20,
                                borderRadius: 4,
                                backgroundColor: alert.enabled ? '#EFF6FF' : '#F1F5F9',
                                color: alert.enabled ? '#2563EB' : '#64748B',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            <IconBell size={12} />
                        </Box>
                        <div style={{ minWidth: 0, flex: 1 }}>
                            <Text
                                fw={600}
                                size="sm"
                                c="#0F172A"
                                style={{
                                    whiteSpace: 'normal',
                                    wordBreak: 'break-word',
                                    overflowWrap: 'anywhere',
                                }}
                            >
                                {alert.name}
                            </Text>
                        </div>
                    </Group>
                    <Switch
                        checked={alert.enabled}
                        onChange={() => {}}
                        onClick={handleToggle}
                        disabled={isToggling}
                        size="xs"
                        color="blue"
                    />
                </Group>

                {/* Network + Type */}
                <Group gap={6} wrap="nowrap">
                    <Group gap={4} wrap="nowrap">
                        <ChainLogo chain={alert.network} size="xs" />
                        <Text size="xs" c="#475569">
                            {getChainIdentity(alert.network)?.name || alert.network}
                        </Text>
                    </Group>
                    <AlertEventBadge
                        eventType={alert.event_type}
                        chain={alert.network}
                        size="xs"
                    />
                    <Badge size="xs" variant="dot" color={getStatusColor(alert.status)}>
                        {alert.status}
                    </Badge>
                </Group>

                {/* Description */}
                <Text size="xs" c="#475569" lineClamp={2}>
                    {alert.description || 'No description'}
                </Text>

                {/* Footer - Compact */}
                <Group justify="space-between" align="center">
                    <Text size="xs" c="#94A3B8" style={{ fontSize: 10 }}>
                        {alert.last_triggered ? new Date(alert.last_triggered).toLocaleDateString() : 'Never triggered'}
                    </Text>

                    <Menu shadow="sm" width={140}>
                        <Menu.Target>
                            <ActionIcon variant="subtle" color="gray" size="xs" onClick={(e) => e.stopPropagation()}>
                                <IconDots size={12} />
                            </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                            <Menu.Item leftSection={<IconEdit size={12} />} onClick={() => onEdit(alert)}>
                                Edit
                            </Menu.Item>
                            <Menu.Item leftSection={<IconCopy size={12} />} onClick={() => onDuplicate(alert)}>
                                Duplicate
                            </Menu.Item>
                            <Menu.Divider />
                            <Menu.Item
                                leftSection={<IconTrash size={12} />}
                                color="red"
                                onClick={() => onDelete(alert.id)}
                            >
                                Delete
                            </Menu.Item>
                        </Menu.Dropdown>
                    </Menu>
                </Group>
            </Stack>
        </Card>
    )
}
