/**
 * Command Palette Component
 *
 * Global search and quick actions modal (Cmd+K / Ctrl+K)
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Modal,
    TextInput,
    Stack,
    Text,
    Group,
    Badge,
    Box,
    Paper,
    Kbd,
    Loader,
    Center,
    Divider,
    ScrollArea,
    UnstyledButton,
    ThemeIcon,
    rem,
} from '@mantine/core'
import { useDisclosure, useHotkeys, useDebouncedValue } from '@mantine/hooks'
import {
    IconSearch,
    IconHome,
    IconBell,
    IconWallet,
    IconSettings,
    IconUser,
    IconUsers,
    IconCode,
    IconCompass,
    IconPhoto,
    IconHelp,
    IconShield,
    IconCreditCard,
    IconMail,
    IconFolder,
    IconPlus,
    IconDownload,
    IconSun,
    IconMoon,
    IconLogout,
    IconCommand,
    IconArrowRight,
    IconCornerDownLeft,
    IconTemplate,
} from '@tabler/icons-react'
import searchApiService, {
    type SearchResult,
    type GlobalSearchResponse,
} from '../../services/search-api'
import { useAuthStore } from '../../store/auth'

// Icon mapping for different result types
const ICON_MAP: Record<string, typeof IconHome> = {
    // Pages
    home: IconHome,
    bell: IconBell,
    wallet: IconWallet,
    settings: IconSettings,
    user: IconUser,
    users: IconUsers,
    code: IconCode,
    compass: IconCompass,
    image: IconPhoto,
    'help-circle': IconHelp,
    shield: IconShield,
    'credit-card': IconCreditCard,
    folder: IconFolder,
    // Actions
    plus: IconPlus,
    download: IconDownload,
    'sun-moon': IconSun,
    'folder-plus': IconFolder,
    'log-out': IconLogout,
    // Entities
    transfer: IconArrowRight,
    chart: IconTemplate,
    template: IconTemplate,
}

const TYPE_COLORS: Record<string, string> = {
    page: 'blue',
    action: 'green',
    alert: 'orange',
    wallet: 'purple',
    transaction: 'cyan',
    template: 'grape',
}

const TYPE_LABELS: Record<string, string> = {
    page: 'Page',
    action: 'Action',
    alert: 'Alert',
    wallet: 'Wallet',
    transaction: 'Tx',
    template: 'Template',
}

interface CommandPaletteProps {
    opened: boolean
    onClose: () => void
}

export function CommandPalette({ opened, onClose }: CommandPaletteProps) {
    const navigate = useNavigate()
    const { logout } = useAuthStore()
    const [query, setQuery] = useState('')
    const [debouncedQuery] = useDebouncedValue(query, 200)
    const [results, setResults] = useState<SearchResult[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(0)
    const inputRef = useRef<HTMLInputElement>(null)
    const scrollAreaRef = useRef<HTMLDivElement>(null)

    // Load initial results (pages and actions)
    useEffect(() => {
        if (opened) {
            setQuery('')
            setSelectedIndex(0)
            // Show pages and actions by default
            const pages = searchApiService.getPages()
            const actions = searchApiService.getActions()
            setResults([...actions.slice(0, 3), ...pages.slice(0, 8)])
            // Focus input
            setTimeout(() => inputRef.current?.focus(), 50)
        }
    }, [opened])

    // Search when query changes
    useEffect(() => {
        const search = async () => {
            if (debouncedQuery.length < 1) {
                // Show default results
                const pages = searchApiService.getPages()
                const actions = searchApiService.getActions()
                setResults([...actions.slice(0, 3), ...pages.slice(0, 8)])
                return
            }

            setIsLoading(true)
            try {
                const response = await searchApiService.globalSearch({
                    query: debouncedQuery,
                    limit: 15,
                })
                setResults(response.results)
                setSelectedIndex(0)
            } catch (error) {
                console.error('Search failed:', error)
            } finally {
                setIsLoading(false)
            }
        }

        search()
    }, [debouncedQuery])

    // Handle keyboard navigation
    const handleKeyDown = useCallback(
        (event: React.KeyboardEvent) => {
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault()
                    setSelectedIndex((prev) => Math.min(prev + 1, results.length - 1))
                    break
                case 'ArrowUp':
                    event.preventDefault()
                    setSelectedIndex((prev) => Math.max(prev - 1, 0))
                    break
                case 'Enter':
                    event.preventDefault()
                    if (results[selectedIndex]) {
                        executeResult(results[selectedIndex])
                    }
                    break
                case 'Escape':
                    onClose()
                    break
            }
        },
        [results, selectedIndex, onClose]
    )

    // Execute selected result
    const executeResult = useCallback(
        (result: SearchResult) => {
            onClose()

            switch (result.type) {
                case 'page':
                    if (result.url) {
                        navigate(result.url)
                    }
                    break
                case 'template':
                    if (result.url) {
                        navigate(result.url)
                    }
                    break

                case 'action': {
                    const action = result.metadata?.action
                    switch (action) {
                        case 'create-alert':
                            navigate('/dashboard/alerts')
                            // Could trigger alert creation modal
                            break
                        case 'add-wallet':
                            navigate('/dashboard/wallets')
                            // Could trigger wallet addition modal
                            break
                        case 'create-alert-group':
                            navigate('/dashboard/alerts/groups')
                            break
                        case 'export-data':
                            navigate('/dashboard/profile')
                            break
                        case 'toggle-theme':
                            // Theme toggle logic would go here
                            break
                        case 'logout':
                            logout()
                            navigate('/auth/login')
                            break
                    }
                    break
                }

                case 'alert':
                    if (result.url) {
                        navigate(result.url)
                    }
                    break

                case 'wallet':
                    if (result.url) {
                        navigate(result.url)
                    }
                    break

                case 'transaction':
                    // Could open transaction details
                    break
            }
        },
        [navigate, logout, onClose]
    )

    // Scroll selected item into view
    useEffect(() => {
        const selectedElement = document.querySelector(`[data-index="${selectedIndex}"]`)
        if (selectedElement) {
            selectedElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        }
    }, [selectedIndex])

    const getIcon = (iconName?: string) => {
        const Icon = iconName ? ICON_MAP[iconName] || IconSearch : IconSearch
        return Icon
    }

    // Group results by type for better display
    const groupedResults = results.reduce(
        (acc, result) => {
            const type = result.type
            if (!acc[type]) {
                acc[type] = []
            }
            acc[type].push(result)
            return acc
        },
        {} as Record<string, SearchResult[]>
    )

    // Flatten grouped results for indexing
    const flatResults = results

    return (
        <Modal
            opened={opened}
            onClose={onClose}
            withCloseButton={false}
            centered
            size="lg"
            padding={0}
            radius="lg"
            styles={{
                content: {
                    overflow: 'hidden',
                    border: '1px solid #E2E8F0',
                    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
                },
                body: {
                    padding: 0,
                },
            }}
        >
            <Box>
                {/* Search Input */}
                <Box p="md" style={{ borderBottom: '1px solid #E2E8F0' }}>
                    <TextInput
                        ref={inputRef}
                        placeholder="Search pages, alerts, wallets, or actions..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        leftSection={
                            isLoading ? (
                                <Loader size="xs" />
                            ) : (
                                <IconSearch size={18} color="#64748B" />
                            )
                        }
                        rightSection={
                            <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                Esc
                            </Kbd>
                        }
                        size="md"
                        styles={{
                            input: {
                                border: 'none',
                                background: '#F8FAFC',
                                fontSize: '1rem',
                                '&:focus': {
                                    border: 'none',
                                },
                            },
                        }}
                    />
                </Box>

                {/* Results */}
                <ScrollArea h={400} ref={scrollAreaRef}>
                    {flatResults.length > 0 ? (
                        <Box p="xs">
                            {Object.entries(groupedResults).map(([type, typeResults], groupIndex) => (
                                <Box key={type} mb="sm">
                                    <Text
                                        size="xs"
                                        fw={600}
                                        c="#94A3B8"
                                        tt="uppercase"
                                        px="sm"
                                        mb="xs"
                                        style={{ letterSpacing: '0.05em' }}
                                    >
                                        {TYPE_LABELS[type] || type}s
                                    </Text>
                                    <Stack gap={2}>
                                        {typeResults.map((result) => {
                                            const globalIndex = flatResults.indexOf(result)
                                            const isSelected = globalIndex === selectedIndex
                                            const Icon = getIcon(result.icon)

                                            return (
                                                <UnstyledButton
                                                    key={result.id}
                                                    data-index={globalIndex}
                                                    onClick={() => executeResult(result)}
                                                    onMouseEnter={() => setSelectedIndex(globalIndex)}
                                                    style={{
                                                        display: 'block',
                                                        width: '100%',
                                                        padding: rem(10),
                                                        borderRadius: rem(8),
                                                        backgroundColor: isSelected
                                                            ? '#EFF6FF'
                                                            : 'transparent',
                                                        transition: 'background-color 0.1s',
                                                    }}
                                                >
                                                    <Group justify="space-between" wrap="nowrap">
                                                        <Group gap="sm" wrap="nowrap" style={{ flex: 1, minWidth: 0 }}>
                                                            <ThemeIcon
                                                                size="md"
                                                                radius="md"
                                                                variant="light"
                                                                color={TYPE_COLORS[type] || 'gray'}
                                                            >
                                                                <Icon size={16} />
                                                            </ThemeIcon>
                                                            <Box style={{ flex: 1, minWidth: 0 }}>
                                                                <Text
                                                                    size="sm"
                                                                    fw={500}
                                                                    c={isSelected ? '#1E40AF' : '#0F172A'}
                                                                    truncate
                                                                >
                                                                    {result.title}
                                                                </Text>
                                                                {result.subtitle && (
                                                                    <Text
                                                                        size="xs"
                                                                        c="#64748B"
                                                                        truncate
                                                                    >
                                                                        {result.subtitle}
                                                                    </Text>
                                                                )}
                                                            </Box>
                                                        </Group>

                                                        <Group gap="xs" wrap="nowrap">
                                                            {result.metadata?.shortcut && (
                                                                <Kbd
                                                                    size="xs"
                                                                    style={{ border: '1px solid #E2E8F0' }}
                                                                >
                                                                    {result.metadata.shortcut}
                                                                </Kbd>
                                                            )}
                                                            {isSelected && (
                                                                <IconCornerDownLeft
                                                                    size={14}
                                                                    color="#64748B"
                                                                />
                                                            )}
                                                        </Group>
                                                    </Group>
                                                </UnstyledButton>
                                            )
                                        })}
                                    </Stack>
                                </Box>
                            ))}
                        </Box>
                    ) : (
                        <Center h={200}>
                            <Stack align="center" gap="sm">
                                <IconSearch size={32} color="#CBD5E1" />
                                <Text c="dimmed" size="sm">
                                    {query
                                        ? 'No results found'
                                        : 'Start typing to search...'}
                                </Text>
                            </Stack>
                        </Center>
                    )}
                </ScrollArea>

                {/* Footer */}
                <Box
                    p="sm"
                    style={{ borderTop: '1px solid #E2E8F0', background: '#F8FAFC' }}
                >
                    <Group justify="space-between">
                        <Group gap="md">
                            <Group gap={4}>
                                <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                    <IconCornerDownLeft size={10} />
                                </Kbd>
                                <Text size="xs" c="dimmed">
                                    Select
                                </Text>
                            </Group>
                            <Group gap={4}>
                                <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                    ↑
                                </Kbd>
                                <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                    ↓
                                </Kbd>
                                <Text size="xs" c="dimmed">
                                    Navigate
                                </Text>
                            </Group>
                            <Group gap={4}>
                                <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                    Esc
                                </Kbd>
                                <Text size="xs" c="dimmed">
                                    Close
                                </Text>
                            </Group>
                        </Group>
                        <Group gap={4}>
                            <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                {navigator.platform.includes('Mac') ? '⌘' : 'Ctrl'}
                            </Kbd>
                            <Text size="xs" c="dimmed">
                                +
                            </Text>
                            <Kbd size="xs" style={{ border: '1px solid #E2E8F0' }}>
                                K
                            </Kbd>
                            <Text size="xs" c="dimmed">
                                Open
                            </Text>
                        </Group>
                    </Group>
                </Box>
            </Box>
        </Modal>
    )
}

// Hook to manage command palette state globally
export function useCommandPalette() {
    const [opened, { open, close, toggle }] = useDisclosure(false)

    // Global keyboard shortcut
    useHotkeys([['mod+k', () => toggle()]])

    return { opened, open, close, toggle }
}
