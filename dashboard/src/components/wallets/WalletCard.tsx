/**
 * Wallet Card Component
 *
 * Displays individual wallet information in a compact card format with selection support
 */

import { Card, Group, Text, Badge, Stack, ActionIcon, Tooltip, Checkbox } from '@mantine/core'
import { IconCopy, IconRefresh, IconEye, IconShield } from '@tabler/icons-react'
import type { Wallet } from '../../store/wallets'
import { useState } from 'react'
import TokenLogo from '../brand/TokenLogo'

interface WalletCardProps {
    wallet: Wallet
    onView: (wallet: Wallet) => void
    onSync: (id: string) => Promise<void>
    onCopyAddress: (address: string) => void
    selected?: boolean
    selectable?: boolean
    onSelect?: () => void
}

export function WalletCard({ wallet, onView, onSync, onCopyAddress, selected, selectable, onSelect }: WalletCardProps) {
    const [isSyncing, setIsSyncing] = useState(false)

    const getBlockchainColor = (blockchain: string) => {
        const colors: Record<string, string> = {
            ethereum: '#627EEA',
            bitcoin: '#F7931A',
            polygon: '#8247E5',
            arbitrum: '#28A0F0',
            optimism: '#FF0420',
            avalanche: '#E84142'
        }
        return colors[blockchain] || '#64748B'
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'active': return 'green'
            case 'inactive': return 'gray'
            case 'syncing': return 'blue'
            case 'error': return 'red'
            default: return 'gray'
        }
    }

    const handleSync = async () => {
        setIsSyncing(true)
        try {
            await onSync(wallet.id)
        } finally {
            setIsSyncing(false)
        }
    }

    const handleClick = () => {
        if (selectable && onSelect) {
            onSelect()
        } else {
            onView(wallet)
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
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                height: '100%',
            }}
            onClick={handleClick}
            styles={{
                root: {
                    '&:hover': {
                        borderColor: selected ? '#2563EB' : getBlockchainColor(wallet.blockchain),
                        transform: 'translateY(-1px)',
                    }
                }
            }}
        >
            <Stack gap={6}>
                {/* Header - Compact */}
                <Group justify="space-between" align="center">
                    <Group gap={6}>
                        {selectable && (
                            <Checkbox
                                checked={selected}
                                onChange={onSelect}
                                size="xs"
                                onClick={(e) => e.stopPropagation()}
                            />
                        )}
                        <TokenLogo symbol={wallet.balance.symbol} size="sm" label={wallet.balance.symbol} />
                        <div style={{ minWidth: 0 }}>
                            <Group gap={4}>
                                <Text fw={600} size="xs" c="#0F172A" lineClamp={1}>{wallet.name}</Text>
                                {wallet.privacy === 'private' && <IconShield size={10} color="#64748B" />}
                            </Group>
                        </div>
                    </Group>
                    <Badge size="xs" color={getStatusColor(wallet.status)} variant="dot">
                        {wallet.status}
                    </Badge>
                </Group>

                {/* Balance - Compact */}
                <Group justify="space-between" align="flex-end">
                    <div>
                        <Text size="sm" fw={700} c="#0F172A" lh={1}>
                            {wallet.balance.amount} {wallet.balance.symbol}
                        </Text>
                        <Text size="xs" c="#64748B">
                            ${wallet.balance.usd_value.toLocaleString()}
                        </Text>
                    </div>
                    <Group gap={2}>
                        <Tooltip label="Copy">
                            <ActionIcon
                                size="xs"
                                variant="subtle"
                                onClick={(e) => { e.stopPropagation(); onCopyAddress(wallet.address) }}
                            >
                                <IconCopy size={12} />
                            </ActionIcon>
                        </Tooltip>
                        <Tooltip label="Sync">
                            <ActionIcon
                                size="xs"
                                variant="subtle"
                                loading={isSyncing}
                                onClick={(e) => { e.stopPropagation(); handleSync() }}
                            >
                                <IconRefresh size={12} />
                            </ActionIcon>
                        </Tooltip>
                    </Group>
                </Group>

                {/* Address - Compact */}
                <Text size="xs" c="#94A3B8" style={{ fontFamily: 'monospace', fontSize: 9 }}>
                    {wallet.address.slice(0, 6)}...{wallet.address.slice(-4)}
                </Text>
            </Stack>
        </Card>
    )
}
