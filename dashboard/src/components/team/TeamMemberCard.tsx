/**
 * Team Member Card Component
 * 
 * Displays individual team member information in a card format
 */

import { Card, Group, Text, Badge, Stack, Avatar, ActionIcon, Menu, Tooltip } from '@mantine/core'
import { IconDots, IconEdit, IconTrash, IconMail, IconShield, IconCrown, IconUser } from '@tabler/icons-react'

export interface TeamMember {
    id: string
    name: string
    email: string
    role: 'owner' | 'admin' | 'member' | 'viewer'
    status: 'active' | 'pending' | 'inactive'
    joinedAt: string
    lastActive: string
    avatar?: string
}

interface TeamMemberCardProps {
    member: TeamMember
    onEdit: (member: TeamMember) => void
    onRemove: (id: string) => void
    onResendInvite: (email: string) => void
}

export function TeamMemberCard({ member, onEdit, onRemove, onResendInvite }: TeamMemberCardProps) {
    const getRoleIcon = (role: string) => {
        switch (role) {
            case 'owner': return <IconCrown size={14} color="#F59E0B" />
            case 'admin': return <IconShield size={14} color="#2563EB" />
            case 'member': return <IconUser size={14} color="#10B981" />
            case 'viewer': return <IconUser size={14} color="#64748B" />
            default: return <IconUser size={14} />
        }
    }

    const getRoleColor = (role: string) => {
        switch (role) {
            case 'owner': return 'yellow'
            case 'admin': return 'blue'
            case 'member': return 'green'
            case 'viewer': return 'gray'
            default: return 'gray'
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'active': return 'green'
            case 'pending': return 'yellow'
            case 'inactive': return 'gray'
            default: return 'gray'
        }
    }

    return (
        <Card
            padding="lg"
            radius="md"
            withBorder
            style={{
                background: '#FFFFFF',
                border: '1px solid #E6E9EE',
                transition: 'all 0.2s ease',
            }}
            styles={{
                root: {
                    '&:hover': {
                        borderColor: '#2563EB',
                        boxShadow: '0 4px 12px rgba(37, 99, 235, 0.1)',
                        transform: 'translateY(-2px)',
                    }
                }
            }}
        >
            <Stack gap="md">
                <Group justify="space-between" align="flex-start">
                    <Group gap="sm">
                        <Avatar
                            size="lg"
                            radius="xl"
                            src={member.avatar}
                            color={getRoleColor(member.role)}
                        >
                            {member.name.split(' ').map(n => n[0]).join('')}
                        </Avatar>
                        <div>
                            <Text fw={600} c="#0F172A">{member.name}</Text>
                            <Text size="sm" c="#64748B">{member.email}</Text>
                        </div>
                    </Group>
                    <Menu shadow="md" width={200}>
                        <Menu.Target>
                            <ActionIcon variant="subtle" color="gray">
                                <IconDots size={16} />
                            </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                            <Menu.Item leftSection={<IconEdit size={14} />} onClick={() => onEdit(member)}>
                                Edit Role
                            </Menu.Item>
                            <Menu.Item leftSection={<IconMail size={14} />} onClick={() => onResendInvite(member.email)}>
                                Resend Invite
                            </Menu.Item>
                            <Menu.Divider />
                            <Menu.Item
                                leftSection={<IconTrash size={14} />}
                                color="red"
                                onClick={() => onRemove(member.id)}
                            >
                                Remove Member
                            </Menu.Item>
                        </Menu.Dropdown>
                    </Menu>
                </Group>

                <Group gap="xs">
                    <Badge
                        size="sm"
                        variant="light"
                        color={getRoleColor(member.role)}
                        leftSection={getRoleIcon(member.role)}
                    >
                        {member.role}
                    </Badge>
                    <Badge
                        size="sm"
                        variant="dot"
                        color={getStatusColor(member.status)}
                    >
                        {member.status}
                    </Badge>
                </Group>

                <Group gap="xl" mt="xs">
                    <div>
                        <Text size="xs" c="#64748B">Joined</Text>
                        <Text size="sm" fw={500} c="#0F172A">
                            {new Date(member.joinedAt).toLocaleDateString()}
                        </Text>
                    </div>
                    <div>
                        <Text size="xs" c="#64748B">Last Active</Text>
                        <Text size="sm" fw={500} c="#0F172A">{member.lastActive}</Text>
                    </div>
                </Group>
            </Stack>
        </Card>
    )
}
