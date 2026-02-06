/**
 * Alert Groups Page
 * 
 * Main page for browsing and managing alert groups
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Container,
    Title,
    Text,
    Button,
    Group,
    Stack,
    Grid,
    TextInput,
    Autocomplete,
    Select,
    MultiSelect,
    Loader,
    Center,
    Alert,
    Tabs,
    Badge,
    Modal,
    Card,
    Divider,
    SegmentedControl,
    NumberInput,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
    IconSearch,
    IconFilter,
    IconPlus,
    IconAlertCircle,
    IconCheck,
    IconBell,
    IconUsers,
} from '@tabler/icons-react'
import {
    useAlertGroupsStore,
    getGroupCategory,
    getGroupTags,
} from '../../store/alertGroups'
import type { AlertGroupTemplatesResponse, GenericGroup } from '../../services/groups-api'
import groupsApiService, { GroupType } from '../../services/groups-api'
import { AlertGroupCard } from '../../components/alerts/AlertGroupCard'
import { AlertGroupWizard } from '../../components/alerts/AlertGroupWizard'
import { IconWallet } from '@tabler/icons-react'
import {
    buildTargetingVariableIds,
    getVariableId,
    isValueProvided,
    type AlertTargetType,
    type TemplateVariable,
} from '../../utils/alert-templates'

function normalizeAlertType(raw: string): AlertTargetType {
    const type = (raw || 'wallet').toLowerCase()
    if (
        type === 'wallet' ||
        type === 'network' ||
        type === 'protocol' ||
        type === 'token' ||
        type === 'contract' ||
        type === 'nft'
    ) {
        return type as AlertTargetType
    }
    return 'wallet'
}

function alertTypeToTargetGroupType(alertType: string): GroupType {
    const normalized = (alertType || '').toLowerCase()
    if (normalized === 'network') return GroupType.NETWORK
    if (normalized === 'protocol') return GroupType.PROTOCOL
    if (normalized === 'token') return GroupType.TOKEN
    if (normalized === 'contract') return GroupType.CONTRACT
    if (normalized === 'nft') return GroupType.NFT
    return GroupType.WALLET
}

function getTargetKeyPlaceholder(alertType: string): string {
    const normalized = (alertType || '').toLowerCase()
    if (normalized === 'network') return 'e.g. ETH:mainnet'
    if (normalized === 'protocol') return 'e.g. ETH:mainnet:aave-v3'
    if (normalized === 'nft') return 'e.g. ETH:mainnet:0xcollection (or …:token_id later)'
    return 'e.g. ETH:mainnet:0xabc…'
}

export function AlertGroupsPage() {
    const navigate = useNavigate()
    const {
        myGroups,
        publicGroups,
        groups,
        subscriptions,
        isLoading,
        error,
        searchQuery,
        filterCategory,
        loadGroups,
        loadSubscriptions,
        createSubscription,
        deleteSubscription,
        setSearchQuery,
        setFilterCategory,
        setError,
    } = useAlertGroupsStore()

    const [activeTab, setActiveTab] = useState<string | null>('discover')
    const [wizardOpened, { open: openWizard, close: closeWizard }] = useDisclosure(false)
    const [subscribeModalOpened, { open: openSubscribeModal, close: closeSubscribeModal }] = useDisclosure(false)
    const [selectedGroup, setSelectedGroup] = useState<GenericGroup | null>(null)
    const [targetGroups, setTargetGroups] = useState<GenericGroup[]>([])
    const [selectedTargetGroup, setSelectedTargetGroup] = useState<string | null>(null)
    const [isSubscribing, setIsSubscribing] = useState(false)

    // Subscribe modal state: target + params
    const [targetMode, setTargetMode] = useState<'group' | 'key'>('group')
    const [selectedTargetKey, setSelectedTargetKey] = useState<string>('')
    const [accountsWalletKeys, setAccountsWalletKeys] = useState<Array<{ value: string; label: string }>>([])
    const [templatesResponse, setTemplatesResponse] = useState<AlertGroupTemplatesResponse | null>(null)
    const [requiredVariables, setRequiredVariables] = useState<TemplateVariable[]>([])
    const [templateParams, setTemplateParams] = useState<Record<string, unknown>>({})
    const [isLoadingTemplates, setIsLoadingTemplates] = useState(false)

    // Compute subscribed groups from subscriptions
    const subscribedGroupIds = new Set(subscriptions.map((s) => s.alert_group))
    const subscribedGroups = groups.filter((g) => subscribedGroupIds.has(g.id))

    useEffect(() => {
        loadGroups()
        loadSubscriptions()
    }, [loadGroups, loadSubscriptions])

    // Check if a group is subscribed
    const isGroupSubscribed = (groupId: string) => subscribedGroupIds.has(groupId)

    // Find subscription for a group
    const getSubscriptionForGroup = (groupId: string) =>
        subscriptions.find((s) => s.alert_group === groupId)

    const resetSubscribeModalState = () => {
        setSelectedGroup(null)
        setSelectedTargetGroup(null)
        setTargetMode('group')
        setSelectedTargetKey('')
        setTargetGroups([])
        setAccountsWalletKeys([])
        setTemplatesResponse(null)
        setRequiredVariables([])
        setTemplateParams({})
        setIsLoadingTemplates(false)
    }

    const setTemplateParam = (variableId: string, value: unknown) => {
        setTemplateParams((prev) => ({ ...prev, [variableId]: value }))
    }

    const missingRequiredVariableIds = new Set(
        requiredVariables
            .map(getVariableId)
            .filter((id): id is string => !!id)
            .filter((id) => !isValueProvided(templateParams[id]))
    )

    const canSubmitSubscription =
        !!selectedGroup &&
        missingRequiredVariableIds.size === 0 &&
        (targetMode === 'group'
            ? !!selectedTargetGroup
            : isValueProvided(selectedTargetKey))

    // Open subscribe modal and fetch wallet groups + template variables
    const handleSubscribe = async (groupId: string) => {
        const group = groups.find((g) => g.id === groupId)
        if (group) {
            resetSubscribeModalState()
            setSelectedGroup(group)
            setIsLoadingTemplates(true)

            try {
                const groupAlertType = typeof group.settings?.alert_type === 'string'
                    ? (group.settings.alert_type as string)
                    : 'wallet'
                const targetGroupType = alertTypeToTargetGroupType(groupAlertType)

                const [targetGroupsResponse, accountsGroup, templates] = await Promise.all([
                    groupsApiService.getGroupsByType(targetGroupType),
                    groupAlertType.toLowerCase() === 'wallet' ? groupsApiService.getAccountsGroup() : Promise.resolve(null),
                    groupsApiService.getAlertGroupTemplates(groupId),
                ])

                if (!templates.templates.length) {
                    notifications.show({
                        title: 'No templates',
                        message: 'This alert group has no templates yet. Ask the creator to add templates before subscribing.',
                        color: 'yellow',
                        icon: <IconAlertCircle size={16} />,
                    })
                    return
                }

                const accountsId = accountsGroup?.id ?? null
                setTargetGroups(targetGroupsResponse.results)
                setSelectedTargetGroup(groupAlertType.toLowerCase() === 'wallet' ? (accountsId || null) : null)

                const accountKeys = (accountsGroup?.member_keys || []).map((key) => {
                    const label = accountsGroup?.member_data?.members?.[key]?.label
                    const parts = key.split(':')
                    const network = parts[0] || 'NET'
                    const address = parts[2] || key
                    const short = address.length > 12 ? `${address.slice(0, 6)}...${address.slice(-4)}` : address
                    const display = label ? `${label} · ${network} · ${short}` : `${network} · ${short}`
                    return { value: key, label: display }
                })
                setAccountsWalletKeys(groupAlertType.toLowerCase() === 'wallet' ? accountKeys : [])

                setTemplatesResponse(templates)

                // Compute required (non-targeting) variables from the first template
                const template = templates.templates[0]
                const variables = (template?.variables || []) as TemplateVariable[]
                const targetingIds = buildTargetingVariableIds(normalizeAlertType(templates.alert_type))
                const required = variables.filter((v) => {
                    if (!v.required) return false
                    const variableId = getVariableId(v)
                    if (!variableId) return false
                    return !targetingIds.has(variableId.toLowerCase())
                })
                setRequiredVariables(required)

                const initialParams: Record<string, unknown> = {}
                for (const v of required) {
                    const variableId = getVariableId(v)
                    if (!variableId) continue
                    const variableType = (v.type || 'string').toLowerCase()
                    if (v.default !== undefined) {
                        initialParams[variableId] = v.default
                    } else if (v.required && variableType === 'boolean') {
                        initialParams[variableId] = false
                    }
                }
                setTemplateParams(initialParams)

                openSubscribeModal()
            } catch (err) {
                console.error('Failed to prepare subscription modal:', err)
                notifications.show({
                    title: 'Error',
                    message: 'Failed to load group templates or wallet groups',
                    color: 'red',
                    icon: <IconAlertCircle size={16} />,
                })
            } finally {
                setIsLoadingTemplates(false)
            }
        }
    }

    // Confirm subscription with selected target group
    const handleConfirmSubscription = async () => {
        if (!selectedGroup) {
            notifications.show({
                title: 'Error',
                message: 'Missing alert group selection',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
            return
        }

        if (missingRequiredVariableIds.size > 0) {
            notifications.show({
                title: 'Error',
                message: 'Please fill in all required settings before subscribing',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
            return
        }

        setIsSubscribing(true)
        try {
            await createSubscription({
                alertGroupId: selectedGroup.id,
                targetGroupId: targetMode === 'group' ? selectedTargetGroup : null,
                targetKey: targetMode === 'key' ? selectedTargetKey : null,
                templateParams: Object.keys(templateParams).length ? templateParams : undefined,
            })

            notifications.show({
                title: 'Subscribed!',
                message: targetMode === 'group' ? 'Alerts applied to target group' : 'Alerts applied to target key',
                color: 'green',
                icon: <IconCheck size={16} />,
            })
            closeSubscribeModal()
            resetSubscribeModalState()
        } catch (err) {
            notifications.show({
                title: 'Error',
                message: 'Failed to subscribe to group',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
        } finally {
            setIsSubscribing(false)
        }
    }

    const handleUnsubscribe = async (groupId: string) => {
        try {
            const subscription = getSubscriptionForGroup(groupId)
            if (subscription) {
                await deleteSubscription(subscription.id)
                notifications.show({
                    title: 'Unsubscribed',
                    message: 'You have been unsubscribed from this group',
                    color: 'orange',
                    icon: <IconCheck size={16} />,
                })
            }
        } catch (err) {
            notifications.show({
                title: 'Error',
                message: 'Failed to unsubscribe from group',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
        }
    }

    const handleViewDetails = (group: GenericGroup) => {
        navigate(`/dashboard/alerts/groups/${group.id}`)
    }

    // Filter groups based on search and category
    const filteredGroups = groups.filter((group) => {
        const groupTags = getGroupTags(group)
        const groupCategory = getGroupCategory(group)

        const matchesSearch = searchQuery === '' ||
            group.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            group.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
            groupTags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))

        const matchesCategory = !filterCategory || groupCategory === filterCategory

        return matchesSearch && matchesCategory
    })

    const activeGroups =
        activeTab === 'my'
            ? myGroups
            : activeTab === 'subscribed'
                ? subscribedGroups
                : publicGroups

    const displayGroups = activeGroups.filter((group) => {
        const groupTags = getGroupTags(group)
        const groupCategory = getGroupCategory(group)

        const matchesSearch = searchQuery === '' ||
            group.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            group.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
            groupTags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()))

        const matchesCategory = !filterCategory || groupCategory === filterCategory

        return matchesSearch && matchesCategory
    })

    // Get unique categories from group settings
    const categories = Array.from(new Set(groups.map(g => getGroupCategory(g))))

    if (isLoading && groups.length === 0) {
        return (
            <Center h={400}>
                <Stack align="center" gap="md">
                    <Loader size="lg" color="blue" />
                    <Text c="dimmed">Loading alert groups...</Text>
                </Stack>
            </Center>
        )
    }

    return (
        <Container size="xl" py="xl">
            <Stack gap="xl">
                {/* Header */}
                <Group justify="space-between">
                    <div>
                        <Title order={1} c="#0F172A">Alert Groups</Title>
                        <Text c="#475569" mt="xs">
                            Subscribe to curated alert collections from the community
                        </Text>
                    </div>
                    <Button
                        leftSection={<IconPlus size={16} />}
                        style={{ backgroundColor: '#2563EB' }}
                        onClick={openWizard}
                    >
                        Create Group
                    </Button>
                </Group>

                {/* Error Alert */}
                {error && (
                    <Alert
                        icon={<IconAlertCircle size={16} />}
                        color="red"
                        onClose={() => setError(null)}
                        withCloseButton
                    >
                        {error}
                    </Alert>
                )}

                {/* Stats */}
                <Grid>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                        <Card
                            padding="md"
                            radius="md"
                            style={{
                                background: '#FFFFFF',
                                border: '1px solid #E6E9EE',
                                borderLeft: '4px solid #2563EB',
                            }}
                        >
                            <Group gap="xs">
                                <IconBell size={20} color="#2563EB" />
                                <div>
                                    <Text size="sm" c="#475569">Total Groups</Text>
                                    <Text size="xl" fw={700} c="#0F172A">{groups.length}</Text>
                                </div>
                            </Group>
                        </Card>
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                        <Card
                            padding="md"
                            radius="md"
                            style={{
                                background: '#FFFFFF',
                                border: '1px solid #E6E9EE',
                                borderLeft: '4px solid #10B981',
                            }}
                        >
                            <Group gap="xs">
                                <IconCheck size={20} color="#10B981" />
                                <div>
                                    <Text size="sm" c="#475569">Subscribed</Text>
                                    <Text size="xl" fw={700} c="#0F172A">{subscribedGroups.length}</Text>
                                </div>
                            </Group>
                        </Card>
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 4 }}>
                        <Card
                            padding="md"
                            radius="md"
                            style={{
                                background: '#FFFFFF',
                                border: '1px solid #E6E9EE',
                                borderLeft: '4px solid #F59E0B',
                            }}
                        >
                            <Group gap="xs">
                                <IconUsers size={20} color="#F59E0B" />
                                <div>
                                    <Text size="sm" c="#475569">Total Alerts</Text>
                                    <Text size="xl" fw={700} c="#0F172A">
                                        {groups.reduce((sum, g) => sum + (g.member_count || 0), 0)}
                                    </Text>
                                </div>
                            </Group>
                        </Card>
                    </Grid.Col>
                </Grid>

                {/* Filters */}
                <Group gap="md">
                    <TextInput
                        placeholder="Search groups..."
                        leftSection={<IconSearch size={16} />}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{ flex: 1, maxWidth: 400 }}
                        styles={{
                            input: {
                                border: '1px solid #E6E9EE',
                                '&:focus': { borderColor: '#2563EB' }
                            }
                        }}
                    />
                    <Select
                        placeholder="All Categories"
                        leftSection={<IconFilter size={16} />}
                        data={[
                            { value: '', label: 'All Categories' },
                            ...categories.map(cat => ({ value: cat, label: cat }))
                        ]}
                        value={filterCategory || ''}
                        onChange={(value) => setFilterCategory(value || null)}
                        clearable
                        style={{ width: 200 }}
                        styles={{
                            input: {
                                border: '1px solid #E6E9EE',
                                '&:focus': { borderColor: '#2563EB' }
                            }
                        }}
                    />
                </Group>

                {/* Tabs */}
                <Tabs value={activeTab} onChange={setActiveTab}>
                    <Tabs.List>
                        <Tabs.Tab value="discover" leftSection={<IconBell size={16} />}>
                            Discover
                            <Badge size="sm" variant="light" color="gray" ml="xs">
                                {publicGroups.length}
                            </Badge>
                        </Tabs.Tab>
                        <Tabs.Tab value="my" leftSection={<IconUsers size={16} />}>
                            My Groups
                            <Badge size="sm" variant="light" color="gray" ml="xs">
                                {myGroups.length}
                            </Badge>
                        </Tabs.Tab>
                        <Tabs.Tab value="subscribed" leftSection={<IconCheck size={16} />}>
                            Subscribed
                            <Badge size="sm" variant="light" color="blue" ml="xs">
                                {subscribedGroups.length}
                            </Badge>
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="discover" pt="xl">
                        <Grid>
                            {displayGroups.map((group) => (
                                <Grid.Col key={group.id} span={{ base: 12, md: 6, lg: 4 }}>
                                    <AlertGroupCard
                                        group={group}
                                        isSubscribed={isGroupSubscribed(group.id)}
                                        onSubscribe={handleSubscribe}
                                        onUnsubscribe={handleUnsubscribe}
                                        onViewDetails={handleViewDetails}
                                    />
                                </Grid.Col>
                            ))}
                        </Grid>
                        {displayGroups.length === 0 && (
                            <Center h={200}>
                                <Text c="dimmed">No groups found</Text>
                            </Center>
                        )}
                    </Tabs.Panel>

                    <Tabs.Panel value="my" pt="xl">
                        <Grid>
                            {displayGroups.map((group) => (
                                <Grid.Col key={group.id} span={{ base: 12, md: 6, lg: 4 }}>
                                    <AlertGroupCard
                                        group={group}
                                        isSubscribed={isGroupSubscribed(group.id)}
                                        onSubscribe={handleSubscribe}
                                        onUnsubscribe={handleUnsubscribe}
                                        onViewDetails={handleViewDetails}
                                    />
                                </Grid.Col>
                            ))}
                        </Grid>
                        {displayGroups.length === 0 && (
                            <Center h={200}>
                                <Text c="dimmed">You haven't created any alert groups yet</Text>
                            </Center>
                        )}
                    </Tabs.Panel>

                    <Tabs.Panel value="subscribed" pt="xl">
                        <Grid>
                            {subscribedGroups.map((group) => (
                                <Grid.Col key={group.id} span={{ base: 12, md: 6, lg: 4 }}>
                                    <AlertGroupCard
                                        group={group}
                                        isSubscribed={true}
                                        onSubscribe={handleSubscribe}
                                        onUnsubscribe={handleUnsubscribe}
                                        onViewDetails={handleViewDetails}
                                    />
                                </Grid.Col>
                            ))}
                        </Grid>
                        {subscribedGroups.length === 0 && (
                            <Center h={200}>
                                <Stack align="center" gap="md">
                                    <Text c="dimmed">You haven't subscribed to any groups yet</Text>
                                    <Button
                                        variant="light"
                                        onClick={() => setActiveTab('all')}
                                    >
                                        Browse Groups
                                    </Button>
                                </Stack>
                            </Center>
                        )}
                    </Tabs.Panel>
                </Tabs>
            </Stack>

            {/* Subscribe Modal */}
            <Modal
                opened={subscribeModalOpened}
                onClose={() => {
                    closeSubscribeModal()
                    resetSubscribeModalState()
                }}
                title={`Subscribe to "${selectedGroup?.name}"`}
                size="lg"
            >
                <Stack gap="md">
                    <Text size="sm" c="dimmed">
                        Choose where to apply alerts from "{selectedGroup?.name}".
                    </Text>

                    <SegmentedControl
                        value={targetMode}
                        onChange={(value) => setTargetMode(value as 'group' | 'key')}
                        data={[
                            { value: 'group', label: 'Target a group' },
                            { value: 'key', label: 'Target a single key' },
                        ]}
                        fullWidth
                    />

                    {targetMode === 'group' ? (
                        targetGroups.length === 0 ? (
                            <Alert icon={<IconAlertCircle size={16} />} color="yellow">
                                No matching target groups available. Create a group first, or target a single key.
                            </Alert>
                        ) : (
                            <Select
                                label="Target Group"
                                placeholder="Select target group..."
                                leftSection={<IconWallet size={16} />}
                                data={targetGroups.map((wg) => ({
                                    value: wg.id,
                                    label: `${wg.name} (${wg.member_count || 0} members)`,
                                }))}
                                value={selectedTargetGroup}
                                onChange={setSelectedTargetGroup}
                                searchable
                            />
                        )
                    ) : (
                        <Autocomplete
                            label="Target Key"
                            placeholder={templatesResponse ? getTargetKeyPlaceholder(templatesResponse.alert_type) : 'Type a target key…'}
                            data={accountsWalletKeys}
                            value={selectedTargetKey}
                            onChange={setSelectedTargetKey}
                            limit={12}
                            nothingFoundMessage="No suggestions"
                        />
                    )}

                    <Divider my="xs" label="Required settings" />

                    {isLoadingTemplates ? (
                        <Center>
                            <Loader size="sm" />
                        </Center>
                    ) : requiredVariables.length === 0 ? (
                        <Text size="sm" c="dimmed">No required settings for this group.</Text>
                    ) : (
                        <Stack gap="sm">
                            {requiredVariables.map((variable) => {
                                const variableId = getVariableId(variable)
                                if (!variableId) return null
                                const variableType = (variable.type || 'string').toLowerCase()
                                const label = variable.label || variableId
                                const isMissing = missingRequiredVariableIds.has(variableId)

                                const options = variable.validation?.options
                                const normalizedOptions = Array.isArray(options)
                                    ? (options as Array<any>).map((o) =>
                                        typeof o === 'string' ? ({ value: o, label: o }) : ({ value: o.value, label: o.label ?? o.value })
                                      )
                                    : []

                                if (variableType === 'boolean') {
                                    return (
                                        <Card key={variableId} withBorder padding="sm" radius="md">
                                            <Group justify="space-between" align="center">
                                                <div>
                                                    <Text fw={600} size="sm">{label}</Text>
                                                    {variable.description && (
                                                        <Text size="xs" c="dimmed">{variable.description}</Text>
                                                    )}
                                                </div>
                                                <SegmentedControl
                                                    value={(templateParams[variableId] ? 'true' : 'false') as string}
                                                    onChange={(value) => setTemplateParam(variableId, value === 'true')}
                                                    data={[
                                                        { value: 'true', label: 'On' },
                                                        { value: 'false', label: 'Off' },
                                                    ]}
                                                />
                                            </Group>
                                        </Card>
                                    )
                                }

                                if (variableType === 'integer' || variableType === 'decimal') {
                                    return (
                                        <NumberInput
                                            key={variableId}
                                            label={label}
                                            description={variable.description}
                                            value={templateParams[variableId] as number | undefined}
                                            onChange={(value) => setTemplateParam(variableId, value)}
                                            error={isMissing ? 'Required' : undefined}
                                            hideControls={false}
                                        />
                                    )
                                }

                                if (variableType === 'enum') {
                                    return (
                                        <Select
                                            key={variableId}
                                            label={label}
                                            description={variable.description}
                                            data={normalizedOptions}
                                            value={(templateParams[variableId] as string | undefined) || null}
                                            onChange={(value) => setTemplateParam(variableId, value)}
                                            error={isMissing ? 'Required' : undefined}
                                            searchable
                                        />
                                    )
                                }

                                if (variableType === 'enum_multi') {
                                    return (
                                        <MultiSelect
                                            key={variableId}
                                            label={label}
                                            description={variable.description}
                                            data={normalizedOptions}
                                            value={(templateParams[variableId] as string[] | undefined) || []}
                                            onChange={(value) => setTemplateParam(variableId, value)}
                                            error={isMissing ? 'Required' : undefined}
                                            searchable
                                        />
                                    )
                                }

                                return (
                                    <TextInput
                                        key={variableId}
                                        label={label}
                                        description={variable.description}
                                        value={(templateParams[variableId] as string | undefined) || ''}
                                        onChange={(e) => setTemplateParam(variableId, e.currentTarget.value)}
                                        error={isMissing ? 'Required' : undefined}
                                    />
                                )
                            })}
                        </Stack>
                    )}

                    <Group justify="flex-end" mt="md">
                        <Button
                            variant="subtle"
                            onClick={() => {
                                closeSubscribeModal()
                                resetSubscribeModalState()
                            }}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleConfirmSubscription}
                            loading={isSubscribing}
                            disabled={!canSubmitSubscription}
                            style={{ backgroundColor: '#2563EB' }}
                        >
                            Subscribe
                        </Button>
                    </Group>
                </Stack>
            </Modal>

            {/* Alert Group Creation Wizard */}
            <AlertGroupWizard
                opened={wizardOpened}
                onClose={closeWizard}
                onSuccess={() => {
                    loadGroups()
                }}
            />
        </Container>
    )
}
