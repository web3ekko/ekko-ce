/**
 * NewsFeed Component
 *
 * Real-time feed of system events, transactions, and alerts with a social-feed style.
 * Replaces the ActivityTimeline.
 */

import { useState, useEffect, useCallback } from 'react'
import {
    Text,
    Group,
    Stack,
    ThemeIcon,
    Badge,
    ActionIcon,
    ScrollArea,
    Box,
    Loader,
    Center,
    Card,
} from '@mantine/core'
import {
    IconArrowsExchange,
    IconAlertTriangle,
    IconShieldCheck,
    IconLogin,
    IconSettings,
    IconRefresh,
    IconNews,
    IconUsers,
} from '@tabler/icons-react'
import { SegmentedControl } from '@mantine/core'
import { motion, AnimatePresence } from 'framer-motion'
import { ExecutiveCard } from '../ui/ExecutiveCard'
import { dashboardApiService, type ActivityItem } from '../../services/dashboard-api'

interface NewsItem {
    id: string
    type: 'transaction' | 'alert' | 'security' | 'system' | 'execution' | 'alert_created' | 'group_joined'
    title: string
    description: string
    timestamp: string
    severity?: 'critical' | 'high' | 'medium' | 'low'
    metadata?: Record<string, any>
}

// Map API activity items to display events
function mapActivityToNews(item: ActivityItem): NewsItem {
    let type: NewsItem['type'] = 'system'
    if (item.type === 'execution') type = 'alert'
    else if (item.type === 'alert_created') type = 'alert'
    else if (item.type === 'group_joined') type = 'system'

    return {
        id: item.id,
        type,
        title: item.title,
        description: item.subtitle,
        timestamp: item.timestamp,
        severity: item.metadata?.triggered ? 'medium' : undefined,
        metadata: item.metadata,
    }
}

export function NewsFeed() {
    const [items, setItems] = useState<NewsItem[]>([])
    const [filter, setFilter] = useState('all')
    const [isLoading, setIsLoading] = useState(true)
    const [isAutoScroll, setIsAutoScroll] = useState(true)

    // Fetch activity from API
    const fetchNews = useCallback(async () => {
        try {
            const response = await dashboardApiService.getActivity({ limit: 50 })
            const mappedItems = response.activities.map(mapActivityToNews)
            setItems(mappedItems)
        } catch (error) {
            console.error('Failed to fetch news feed:', error)
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Initial fetch
    useEffect(() => {
        fetchNews()
    }, [fetchNews])

    // Refresh activity periodically
    useEffect(() => {
        if (!isAutoScroll) return

        const interval = setInterval(() => {
            fetchNews()
        }, 30000) // Refresh every 30 seconds

        return () => clearInterval(interval)
    }, [isAutoScroll, fetchNews])

    const getEventIcon = (type: string) => {
        switch (type) {
            case 'transaction': return <IconArrowsExchange size={18} />
            case 'alert': return <IconAlertTriangle size={18} />
            case 'security': return <IconShieldCheck size={18} />
            case 'system': return <IconSettings size={18} />
            default: return <IconLogin size={18} />
        }
    }

    const getEventColor = (type: string, severity?: string) => {
        if (severity === 'critical') return 'red'
        if (severity === 'high') return 'orange'

        switch (type) {
            case 'transaction': return 'blue'
            case 'alert': return 'yellow'
            case 'security': return 'teal'
            case 'system': return 'gray'
            default: return 'blue'
        }
    }

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp)
        const now = new Date()
        const diff = now.getTime() - date.getTime()

        // If less than 24h, show relative time
        if (diff < 24 * 60 * 60 * 1000) {
            if (diff < 60 * 1000) return 'Just now'
            if (diff < 60 * 60 * 1000) return `${Math.floor(diff / 60000)}m ago`
            return `${Math.floor(diff / 3600000)}h ago`
        }

        return date.toLocaleDateString()
    }

    return (
        <ExecutiveCard
            size="default"
            style={{ height: '100%', display: 'flex', flexDirection: 'column' } as React.CSSProperties}
        >
            <Group justify="space-between" mb="md">
                <Group gap="xs">
                    <IconNews size={20} color="#2563EB" />
                    <Text fw={700} size="lg">Newsfeed</Text>
                </Group>

                <Group gap="xs">
                    <SegmentedControl
                        size="xs"
                        value={filter}
                        onChange={setFilter}
                        data={[
                            { label: 'All', value: 'all' },
                            {
                                label: (
                                    <Center style={{ gap: 6 }}>
                                        <IconUsers size={14} />
                                        <span>Team</span>
                                    </Center>
                                ),
                                value: 'team'
                            },
                        ]}
                    />
                    <ActionIcon
                        variant="subtle"
                        size="sm"
                        color={isAutoScroll ? 'blue' : 'gray'}
                        onClick={() => setIsAutoScroll(!isAutoScroll)}
                        title={isAutoScroll ? "Live updates on" : "Live updates off"}
                    >
                        <IconRefresh size={16} style={{ animation: isAutoScroll ? 'spin 4s linear infinite' : 'none' }} />
                    </ActionIcon>
                </Group>
            </Group>

            <ScrollArea h={400} offsetScrollbars type="hover">
                {isLoading ? (
                    <Center h={200}>
                        <Loader size="sm" />
                    </Center>
                ) : items.length === 0 ? (
                    <Center h={300}>
                        <Stack align="center" gap="md">
                            <Box p="xl" style={{ background: '#F1F5F9', borderRadius: '50%' }}>
                                <IconNews size={32} color="#64748B" />
                            </Box>
                            <Text size="lg" fw={600} c="#0F172A">No news yet</Text>
                            <Text size="sm" c="dimmed" ta="center" maw={300}>
                                Your activity feed will populate here. Connect a wallet or create an alert to get started.
                            </Text>
                        </Stack>
                    </Center>
                ) : (
                    <Stack gap="md">
                        <AnimatePresence initial={false}>
                            {items
                                .filter(item => filter === 'all' || (filter === 'team' && (item.type === 'system' || item.type === 'group_joined')))
                                .map((item, index) => (
                                    <motion.div
                                        key={item.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.2, delay: index * 0.05 }}
                                    >
                                        <Card
                                            radius="md"
                                            p="md"
                                            withBorder
                                            style={{
                                                borderColor: item.severity === 'critical' ? '#FFA8A8' : item.severity === 'high' ? '#FFD8A8' : item.severity === 'medium' ? '#A5D8FF' : '#E6E9EE',
                                                backgroundColor: item.severity === 'critical' ? '#FFF5F5' : item.severity === 'high' ? '#FFF9DB' : item.severity === 'medium' ? '#E7F5FF' : '#FFFFFF',
                                                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                                            }}
                                            styles={{
                                                root: {
                                                    '&:hover': {
                                                        transform: 'translateY(-2px)',
                                                        boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                                                    }
                                                }
                                            }}
                                        >
                                            <Group align="flex-start" wrap="nowrap">
                                                <ThemeIcon
                                                    size="lg"
                                                    radius="md"
                                                    variant="light"
                                                    color={getEventColor(item.type, item.severity)}
                                                >
                                                    {getEventIcon(item.type)}
                                                </ThemeIcon>

                                                <Box style={{ flex: 1 }}>
                                                    <Group justify="space-between" align="center" mb={2}>
                                                        {item.type === 'alert' && <IconAlertTriangle size={14} color={getEventColor(item.type, item.severity)} />}
                                                        {item.type === 'transaction' && <IconArrowsExchange size={14} color={getEventColor(item.type, item.severity)} />}
                                                        {item.type === 'system' && <IconSettings size={14} color={getEventColor(item.type, item.severity)} />}
                                                        <Text size="sm" fw={600} c="#0F172A">
                                                            {item.title}
                                                        </Text>
                                                        <Text size="xs" c="dimmed" fw={500}>
                                                            {formatTime(item.timestamp)}
                                                        </Text>
                                                    </Group>

                                                    <Text size="sm" c="#475569" lh={1.4}>
                                                        {item.description}
                                                    </Text>

                                                    {item.metadata && (
                                                        <Group gap="xs" mt="xs">
                                                            {/* Render tags based on metadata */}
                                                            {Object.entries(item.metadata).map(([key, value]) => {
                                                                if (['alert_id', 'triggered'].includes(key)) return null;
                                                                return (
                                                                    <Badge key={key} size="xs" variant="dot" color="gray">
                                                                        {String(value)}
                                                                    </Badge>
                                                                )
                                                            })}
                                                        </Group>
                                                    )}
                                                </Box>
                                            </Group>
                                        </Card>
                                    </motion.div>
                                ))}
                        </AnimatePresence>
                    </Stack>
                )}
            </ScrollArea>
        </ExecutiveCard>
    )
}
