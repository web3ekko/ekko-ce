/**
 * Wallet Group Card Component
 * 
 * Displays wallet group information in a card format
 */

import { Card, Group, Text, Badge, Stack, Avatar, ActionIcon, Menu, Tooltip, ThemeIcon } from '@mantine/core'
import { IconDots, IconEdit, IconTrash, IconEye, IconWallet, IconLock } from '@tabler/icons-react'
import type { GenericGroup } from '../../services/groups-api'

interface WalletGroupCardProps {
    group: GenericGroup
    walletCount: number
    onView: (group: GenericGroup) => void
    onEdit: (group: GenericGroup) => void
    onDelete: (id: string) => void
}

export function WalletGroupCard({ group, walletCount, onView, onEdit, onDelete }: WalletGroupCardProps) {
    const settings = group.settings as { color?: string; icon?: string; visibility?: string; system_key?: string } | undefined
    const color = settings?.color || '#2563EB'
    const icon = settings?.icon || '📁'
    const visibility = settings?.visibility || 'private'
    const isSystemAccounts = settings?.system_key === 'accounts'

    return (
        <Card
            padding="lg"
            radius="md"
            withBorder
            style={{
                background: '#FFFFFF',
                border: '1px solid #E6E9EE',
                transition: 'all 0.2s ease',
                cursor: 'pointer',
            }}
            onClick={() => onView(group)}
            styles={{
                root: {
                    '&:hover': {
                        borderColor: color,
                        boxShadow: `0 4px 12px ${color}20`,
                        transform: 'translateY(-2px)',
                    }
                }
            }}
        >
            <Stack gap="md">
                <Group justify="space-between" align="flex-start">
                    <Group gap="sm">
                        <ThemeIcon
                            size="xl"
                            radius="md"
                            variant="light"
                            color={color}
                        >
                            <Text size="xl">{icon}</Text>
                        </ThemeIcon>
                        <div>
                            <Text fw={600} c="#0F172A">{group.name}</Text>
                            <Text size="xs" c="#64748B">Created {new Date(group.created_at).toLocaleDateString()}</Text>
                            <Group gap={6} mt={4}>
                                <Badge size="xs" variant="light" color={visibility === 'public' ? 'blue' : 'gray'}>
                                    {visibility}
                                </Badge>
                                {isSystemAccounts && (
                                    <Badge size="xs" variant="light" color="gray" leftSection={<IconLock size={12} />}>
                                        Accounts
                                    </Badge>
                                )}
                            </Group>
                        </div>
                    </Group>

                    <Menu shadow="md" width={200}>
                        <Menu.Target>
                            <ActionIcon
                                variant="subtle"
                                color="gray"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <IconDots size={16} />
                            </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                            <Menu.Item leftSection={<IconEye size={14} />} onClick={() => onView(group)}>
                                View Details
                            </Menu.Item>
                            {!isSystemAccounts && (
                                <Menu.Item leftSection={<IconEdit size={14} />} onClick={() => onEdit(group)}>
                                    Edit Group
                                </Menu.Item>
                            )}
                            <Menu.Divider />
                            {!isSystemAccounts && (
                                <Menu.Item
                                    leftSection={<IconTrash size={14} />}
                                    color="red"
                                    onClick={() => onDelete(group.id)}
                                >
                                    Delete Group
                                </Menu.Item>
                            )}
                        </Menu.Dropdown>
                    </Menu>
                </Group>

                <Text size="sm" c="#475569" lineClamp={2} style={{ minHeight: 40 }}>
                    {group.description || 'No description provided'}
                </Text>

                <Group justify="space-between" align="center">
                    <Badge
                        size="sm"
                        variant="light"
                        color={color}
                        leftSection={<IconWallet size={12} />}
                    >
                        {walletCount} Wallets
                    </Badge>

                    <Group gap={-8}>
                        {[...Array(Math.min(3, walletCount))].map((_, i) => (
                            <Avatar
                                key={i}
                                size="sm"
                                radius="xl"
                                style={{ border: '2px solid white' }}
                                color={color}
                            >
                                <IconWallet size={12} />
                            </Avatar>
                        ))}
                        {walletCount > 3 && (
                            <Avatar
                                size="sm"
                                radius="xl"
                                style={{ border: '2px solid white' }}
                                color="gray"
                            >
                                <Text size="xs">+{walletCount - 3}</Text>
                            </Avatar>
                        )}
                    </Group>
                </Group>
            </Stack>
        </Card>
    )
}
