/**
 * Alert Group Creation Wizard
 *
 * Multi-step wizard for creating new alert groups
 * Steps: Basic Info → Template Selection → Visibility & Permissions → Review & Create
 */

import { useState, useEffect } from 'react'
import {
    Modal,
    Stepper,
    Button,
    Group,
    TextInput,
    Textarea,
    Select,
    MultiSelect,
    Switch,
    Stack,
    Text,
    Card,
    Grid,
    Badge,
    Checkbox,
    Divider,
    Alert,
    ThemeIcon,
    Box,
    Paper,
    SimpleGrid,
    Loader,
    Center,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import {
    IconFolder,
    IconTemplate,
    IconEye,
    IconCheck,
    IconAlertCircle,
    IconChevronRight,
    IconChevronLeft,
    IconBell,
    IconWorld,
    IconLock,
    IconTags,
    IconUsers,
    IconInfoCircle,
} from '@tabler/icons-react'
import groupsApiService, { GroupType } from '../../services/groups-api'
import { API_ENDPOINTS } from '../../config/api'
import { httpClient } from '../../services/http-client'

type AlertGroupAlertType = 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft'
type GroupVisibility = 'private' | 'public'

type TemplateVariable = {
    id?: string
    name?: string
    label?: string
    description?: string
    type?: string
    required?: boolean
    default?: unknown
    validation?: {
        options?: Array<{ value: string; label?: string }> | string[]
    }
}

// Minimal shape from /api/templates/
interface AlertTemplate {
    id: string
    name: string
    description: string
    event_type: string
    sub_event: string
    template_type: string
    alert_type: string
    spec?: {
        variables?: TemplateVariable[]
    } | null
    variables?: TemplateVariable[] | null
    usage_count: number
    is_public: boolean
    is_verified: boolean
    created_by_email?: string
}

interface AlertGroupWizardProps {
    opened: boolean
    onClose: () => void
    onSuccess?: () => void
}

interface FormValues {
    name: string
    description: string
    category: string
    tags: string[]
    visibility: GroupVisibility
    alert_type: AlertGroupAlertType
    selectedTemplates: string[]
}

const CATEGORIES = [
    { value: 'DeFi', label: 'DeFi' },
    { value: 'NFT', label: 'NFT' },
    { value: 'Security', label: 'Security' },
    { value: 'Network', label: 'Network' },
    { value: 'Trading', label: 'Trading' },
    { value: 'Development', label: 'Development' },
    { value: 'Analytics', label: 'Analytics' },
    { value: 'Other', label: 'Other' },
]

const SUGGESTED_TAGS = [
    'whale-watching',
    'defi',
    'nft',
    'security',
    'gas',
    'price-alert',
    'governance',
    'staking',
    'lending',
    'swap',
    'high-value',
    'low-cap',
]

const ALERT_TYPES: Array<{ value: AlertGroupAlertType; label: string; description: string }> = [
    { value: 'wallet', label: 'Wallet', description: 'Targets wallet keys and wallet groups' },
    { value: 'network', label: 'Network', description: 'Targets network keys (e.g. ETH:mainnet) and network groups' },
    { value: 'protocol', label: 'Protocol', description: 'Targets protocol keys (e.g. ETH:mainnet:aave-v3) and protocol groups' },
    { value: 'token', label: 'Token', description: 'Targets token contract keys and token groups' },
    { value: 'contract', label: 'Contract', description: 'Targets contract keys and contract groups' },
    { value: 'nft', label: 'NFT', description: 'Targets NFT collections (and later token_id) via NFT groups' },
]

function getVariableId(variable: TemplateVariable): string | null {
    const raw = variable.id ?? variable.name
    if (!raw || typeof raw !== 'string') return null
    const trimmed = raw.trim()
    return trimmed.length ? trimmed : null
}

function buildTargetingVariableIds(alertType: AlertGroupAlertType): Set<string> {
    const base = new Set([
        'network', 'networks', 'network_key',
        'chain', 'chains', 'chain_id',
        'subnet', 'network_id',
    ])

    if (alertType === 'wallet') {
        ;[
            'wallet', 'wallet_key', 'wallet_address', 'address',
            'wallet_group', 'wallet_group_id',
            'wallets', 'addresses',
            'target_wallet', 'target_key', 'target', 'targets',
        ].forEach((id) => base.add(id))
        return base
    }

    if (alertType === 'network') {
        base.add('network_key')
        return base
    }

    if (alertType === 'protocol') {
        ;['protocol_key', 'protocol', 'protocol_name', 'protocol_id'].forEach((id) => base.add(id))
        return base
    }

    if (alertType === 'token') {
        ;[
            'token', 'token_key', 'token_address', 'token_contract', 'token_contract_address',
            'token_id', 'asset', 'asset_address', 'tokens',
        ].forEach((id) => base.add(id))
        return base
    }

    if (alertType === 'contract' || alertType === 'nft') {
        ;[
            'contract', 'contract_key', 'contract_address', 'contract_addresses', 'contracts',
            'protocol', 'protocol_address', 'protocol_addresses', 'protocol_contract',
            'collection', 'collection_key', 'collection_address', 'collection_addresses',
            'nft_contract', 'nft_contract_address',
            'token_id',
        ].forEach((id) => base.add(id))
        return base
    }

    return base
}

function extractTemplateVariables(template: AlertTemplate): TemplateVariable[] {
    const specVars = template.spec?.variables
    if (Array.isArray(specVars)) return specVars
    if (Array.isArray(template.variables)) return template.variables
    return []
}

function getTemplateTargetAlertType(template: AlertTemplate): AlertGroupAlertType {
    const templateType = (template.template_type || '').toLowerCase()
    if (templateType === 'wallet') return 'wallet'
    if (templateType === 'token') return 'token'
    if (templateType === 'network') return 'network'
    if (templateType === 'protocol') return 'protocol'
    if (templateType === 'contract') return 'contract'
    if (templateType === 'anomaly') return 'network'

    const fallback = (template.alert_type || '').toLowerCase()
    if (
        fallback === 'wallet' ||
        fallback === 'network' ||
        fallback === 'protocol' ||
        fallback === 'token' ||
        fallback === 'contract' ||
        fallback === 'nft'
    ) {
        return fallback as AlertGroupAlertType
    }

    return 'wallet'
}

function getTemplateRequiredParamIds(template: AlertTemplate): Set<string> {
    const targetAlertType = getTemplateTargetAlertType(template)
    const targetingIds = buildTargetingVariableIds(targetAlertType)

    const requiredIds = new Set<string>()
    for (const variable of extractTemplateVariables(template)) {
        if (!variable || typeof variable !== 'object') continue
        if (!variable.required) continue
        const id = getVariableId(variable)
        if (!id) continue
        if (targetingIds.has(id.toLowerCase())) continue
        requiredIds.add(id.toLowerCase())
    }
    return requiredIds
}

function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
    if (a.size !== b.size) return false
    for (const v of a) {
        if (!b.has(v)) return false
    }
    return true
}

export function AlertGroupWizard({ opened, onClose, onSuccess }: AlertGroupWizardProps) {
    const [active, setActive] = useState(0)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [templates, setTemplates] = useState<AlertTemplate[]>([])
    const [loadingTemplates, setLoadingTemplates] = useState(false)
    const [templatesError, setTemplatesError] = useState<string | null>(null)

    const form = useForm<FormValues>({
        initialValues: {
            name: '',
            description: '',
            category: '',
            tags: [],
            visibility: 'private',
            alert_type: 'wallet',
            selectedTemplates: [],
        },
        validate: (values) => {
            if (active === 0) {
                return {
                    name: values.name.length < 3 ? 'Name must be at least 3 characters' : null,
                    description: values.description.length < 10 ? 'Description must be at least 10 characters' : null,
                    category: !values.category ? 'Please select a category' : null,
                    alert_type: !values.alert_type ? 'Please select an alert type' : null,
                }
            }
            return {}
        },
    })

    // Load templates when reaching step 1
    useEffect(() => {
        if (active === 1 && templates.length === 0) {
            loadTemplates()
        }
    }, [active])

    const loadTemplates = async () => {
        setLoadingTemplates(true)
        try {
            // Load alert templates from API
            const response = await httpClient.get<any>(API_ENDPOINTS.ALERT_TEMPLATES.LIST)
            const payload = response.data
            const results: AlertTemplate[] = Array.isArray(payload) ? payload : (payload?.results || [])
            setTemplates(results)
            setTemplatesError(null)
        } catch (error) {
            console.error('Failed to load alert templates:', error)
            setTemplates([])
            setTemplatesError('Failed to load alert templates. Please try again.')
            notifications.show({
                title: 'Error',
                message: 'Failed to load alert templates',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
        } finally {
            setLoadingTemplates(false)
        }
    }

    const nextStep = () => {
        if (active === 0) {
            const validation = form.validate()
            if (validation.hasErrors) return
        }
        if (active === 1) {
            if (form.values.selectedTemplates.length === 0) {
                notifications.show({
                    title: 'Select templates',
                    message: 'Choose at least one template to include in this group',
                    color: 'yellow',
                    icon: <IconAlertCircle size={16} />,
                })
                return
            }
        }
        setActive((current) => (current < 3 ? current + 1 : current))
    }

    const prevStep = () => setActive((current) => (current > 0 ? current - 1 : current))

    const handleSubmit = async () => {
        setIsSubmitting(true)
        try {
            const validation = form.validate()
            if (validation.hasErrors) {
                notifications.show({
                    title: 'Fix errors',
                    message: 'Please review the form fields before creating the group',
                    color: 'red',
                    icon: <IconAlertCircle size={16} />,
                })
                return
            }

            if (form.values.selectedTemplates.length === 0) {
                notifications.show({
                    title: 'Select templates',
                    message: 'Choose at least one template to include in this group',
                    color: 'yellow',
                    icon: <IconAlertCircle size={16} />,
                })
                return
            }

            await groupsApiService.createGroup({
                group_type: GroupType.ALERT,
                name: form.values.name,
                description: form.values.description,
                settings: {
                    alert_type: form.values.alert_type,
                    category: form.values.category,
                    tags: form.values.tags,
                    visibility: form.values.visibility,
                },
                // Add selected templates as initial members (template IDs as member keys)
                initial_members: form.values.selectedTemplates.map((templateId) => ({
                    member_key: `template:${templateId}`,
                    label: templates.find((t) => t.id === templateId)?.name || templateId,
                })),
            })

            notifications.show({
                title: 'Success!',
                message: `Alert group "${form.values.name}" has been created`,
                color: 'green',
                icon: <IconCheck size={16} />,
            })

            onSuccess?.()
            handleClose()
        } catch (error) {
            notifications.show({
                title: 'Error',
                message: 'Failed to create alert group',
                color: 'red',
                icon: <IconAlertCircle size={16} />,
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleClose = () => {
        form.reset()
        setActive(0)
        onClose()
    }

    const toggleTemplate = (templateId: string) => {
        const current = form.values.selectedTemplates
        if (current.includes(templateId)) {
            form.setFieldValue('selectedTemplates', current.filter(id => id !== templateId))
        } else {
            form.setFieldValue('selectedTemplates', [...current, templateId])
        }
    }

    return (
        <Modal
            opened={opened}
            onClose={handleClose}
            title={
                <Group gap="sm">
                    <ThemeIcon size="lg" radius="md" variant="light" color="blue">
                        <IconFolder size={20} />
                    </ThemeIcon>
                    <div>
                        <Text fw={600} size="lg">Create Alert Group</Text>
                        <Text size="xs" c="dimmed">Build a collection of alerts to share or subscribe</Text>
                    </div>
                </Group>
            }
            size="xl"
            centered
            styles={{
                header: {
                    borderBottom: '1px solid #E6E9EE',
                    paddingBottom: 16,
                },
                body: {
                    padding: 24,
                },
            }}
        >
            <Stepper
                active={active}
                onStepClick={setActive}
                size="sm"
                mt="md"
                styles={{
                    step: { padding: '4px 0' },
                    stepLabel: { fontSize: '0.875rem' },
                    stepDescription: { fontSize: '0.75rem' },
                }}
            >
                {/* Step 1: Basic Info */}
                <Stepper.Step
                    label="Basic Info"
                    description="Name and category"
                    icon={<IconFolder size={18} />}
                >
                    <Stack gap="md" mt="xl">
                        <TextInput
                            label="Group Name"
                            placeholder="e.g., DeFi Whale Alerts"
                            required
                            {...form.getInputProps('name')}
                            styles={{
                                input: {
                                    border: '1px solid #E6E9EE',
                                    '&:focus': { borderColor: '#2563EB' },
                                },
                            }}
                        />

                        <Textarea
                            label="Description"
                            placeholder="Describe what this alert group monitors and who it's for..."
                            required
                            minRows={3}
                            {...form.getInputProps('description')}
                            styles={{
                                input: {
                                    border: '1px solid #E6E9EE',
                                    '&:focus': { borderColor: '#2563EB' },
                                },
                            }}
                        />

                        <Select
                            label="Alert Type"
                            description={ALERT_TYPES.find((t) => t.value === form.values.alert_type)?.description}
                            placeholder="Select what this group targets"
                            required
                            data={ALERT_TYPES.map((t) => ({ value: t.value, label: t.label }))}
                            value={form.values.alert_type}
                            onChange={(value) => {
                                const nextValue = (value || 'wallet') as AlertGroupAlertType
                                if (nextValue !== form.values.alert_type) {
                                    form.setFieldValue('alert_type', nextValue)
                                    form.setFieldValue('selectedTemplates', [])
                                }
                            }}
                            styles={{
                                input: {
                                    border: '1px solid #E6E9EE',
                                    '&:focus': { borderColor: '#2563EB' },
                                },
                            }}
                        />

                        <Select
                            label="Category"
                            placeholder="Select a category"
                            required
                            data={CATEGORIES}
                            {...form.getInputProps('category')}
                            styles={{
                                input: {
                                    border: '1px solid #E6E9EE',
                                    '&:focus': { borderColor: '#2563EB' },
                                },
                            }}
                        />

                        <MultiSelect
                            label="Tags"
                            placeholder="Add tags to help others discover your group"
                            data={SUGGESTED_TAGS}
                            searchable
                            creatable
                            getCreateLabel={(query) => `+ Create "${query}"`}
                            {...form.getInputProps('tags')}
                            styles={{
                                input: {
                                    border: '1px solid #E6E9EE',
                                    '&:focus': { borderColor: '#2563EB' },
                                },
                            }}
                        />
                    </Stack>
                </Stepper.Step>

                {/* Step 2: Template Selection */}
                <Stepper.Step
                    label="Templates"
                    description="Add alert templates"
                    icon={<IconTemplate size={18} />}
                >
                    <Stack gap="md" mt="xl">
                        <Alert
                            icon={<IconInfoCircle size={16} />}
                            color="blue"
                            variant="light"
                        >
                            Select alert templates to include in your group. Users who subscribe will receive alerts from these templates.
                        </Alert>

                        <Alert icon={<IconInfoCircle size={16} />} color="gray" variant="light">
                            Alert groups require templates to share the same template type and required settings so subscribers only fill one configuration form.
                        </Alert>

                        {templatesError && (
                            <Alert icon={<IconAlertCircle size={16} />} color="red" variant="light">
                                <Group justify="space-between" align="center">
                                    <Text size="sm">{templatesError}</Text>
                                    <Button size="xs" variant="light" onClick={loadTemplates}>
                                        Retry
                                    </Button>
                                </Group>
                            </Alert>
                        )}

                        {loadingTemplates ? (
                            <Center h={200}>
                                <Loader size="lg" />
                            </Center>
                        ) : (
                            <>
                                {(() => {
                                    const eligibleTemplates = templates.filter(
                                        (template) => getTemplateTargetAlertType(template) === form.values.alert_type
                                    )

                                    const baselineId = form.values.selectedTemplates[0]
                                    const baselineTemplate = baselineId ? templates.find((t) => t.id === baselineId) : undefined
                                    const baselineTemplateType = baselineTemplate?.template_type?.toLowerCase() || null
                                    const baselineRequired = baselineTemplate ? getTemplateRequiredParamIds(baselineTemplate) : null

                                    return (
                                        <>
                                            <Text size="sm" c="dimmed">
                                                {form.values.selectedTemplates.length} selected • {eligibleTemplates.length} available
                                            </Text>

                                            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
                                                {eligibleTemplates.map((template) => {
                                                    const isSelected = form.values.selectedTemplates.includes(template.id)

                                                    let disabledReason: string | null = null
                                                    if (baselineTemplate && template.id !== baselineTemplate.id) {
                                                        if (baselineTemplateType && template.template_type?.toLowerCase() !== baselineTemplateType) {
                                                            disabledReason = `Template type mismatch (${template.template_type} ≠ ${baselineTemplate.template_type})`
                                                        } else if (baselineRequired && !setsEqual(getTemplateRequiredParamIds(template), baselineRequired)) {
                                                            disabledReason = 'Required settings mismatch'
                                                        }
                                                    }

                                                    const isDisabled = !!disabledReason

                                                    return (
                                                        <Card
                                                            key={template.id}
                                                            padding="md"
                                                            radius="md"
                                                            withBorder
                                                            style={{
                                                                cursor: isDisabled ? 'not-allowed' : 'pointer',
                                                                opacity: isDisabled ? 0.55 : 1,
                                                                border: isSelected ? '2px solid #2563EB' : '1px solid #E6E9EE',
                                                                background: isSelected ? '#EFF6FF' : '#FFFFFF',
                                                            }}
                                                            onClick={() => {
                                                                if (isDisabled) return
                                                                toggleTemplate(template.id)
                                                            }}
                                                        >
                                                            <Group justify="space-between" align="flex-start">
                                                                <Stack gap="xs" style={{ flex: 1 }}>
                                                                    <Group gap="xs" wrap="nowrap">
                                                                        <Checkbox
                                                                            checked={isSelected}
                                                                            disabled={isDisabled}
                                                                            onChange={() => {
                                                                                if (isDisabled) return
                                                                                toggleTemplate(template.id)
                                                                            }}
                                                                            onClick={(e) => e.stopPropagation()}
                                                                        />
                                                                        <div style={{ flex: 1 }}>
                                                                            <Text fw={500} size="sm" lineClamp={1}>
                                                                                {template.name}
                                                                            </Text>
                                                                            {disabledReason && (
                                                                                <Text size="xs" c="dimmed" lineClamp={1}>
                                                                                    {disabledReason}
                                                                                </Text>
                                                                            )}
                                                                        </div>
                                                                    </Group>
                                                                    <Text size="xs" c="dimmed" lineClamp={2}>
                                                                        {template.description}
                                                                    </Text>
                                                                    <Group gap={6}>
                                                                        <Badge size="xs" variant="light" color="blue">
                                                                            {template.template_type}
                                                                        </Badge>
                                                                        <Badge size="xs" variant="light" color="gray">
                                                                            {template.event_type}
                                                                        </Badge>
                                                                        {template.is_verified && (
                                                                            <Badge size="xs" variant="light" color="green">
                                                                                Verified
                                                                            </Badge>
                                                                        )}
                                                                    </Group>
                                                                </Stack>
                                                            </Group>
                                                        </Card>
                                                    )
                                                })}
                                            </SimpleGrid>

                                            {eligibleTemplates.length === 0 && (
                                                <Center h={150}>
                                                    <Text c="dimmed">No templates available for this alert type</Text>
                                                </Center>
                                            )}
                                        </>
                                    )
                                })()}

                                {templates.length === 0 && (
                                    <Center h={150}>
                                        <Text c="dimmed">No templates available</Text>
                                    </Center>
                                )}
                            </>
                        )}
                    </Stack>
                </Stepper.Step>

                {/* Step 3: Visibility & Permissions */}
                <Stepper.Step
                    label="Visibility"
                    description="Privacy settings"
                    icon={<IconEye size={18} />}
                >
                    <Stack gap="xl" mt="xl">
                        <Card
                            padding="lg"
                            radius="md"
                            withBorder
                            style={{
                                border: form.values.visibility === 'public' ? '2px solid #2563EB' : '1px solid #E6E9EE',
                                background: form.values.visibility === 'public' ? '#EFF6FF' : '#FFFFFF',
                                cursor: 'pointer',
                            }}
                            onClick={() => form.setFieldValue('visibility', 'public')}
                        >
                            <Group>
                                <ThemeIcon size="xl" radius="md" variant="light" color="blue">
                                    <IconWorld size={24} />
                                </ThemeIcon>
                                <Stack gap={2} style={{ flex: 1 }}>
                                    <Group gap="sm">
                                        <Text fw={600}>Public</Text>
                                        {form.values.visibility === 'public' && (
                                            <Badge size="sm" color="blue">Selected</Badge>
                                        )}
                                    </Group>
                                    <Text size="sm" c="dimmed">
                                        Anyone can discover and subscribe to this group. Great for sharing valuable alerts with the community.
                                    </Text>
                                </Stack>
                                <Checkbox
                                    checked={form.values.visibility === 'public'}
                                    onChange={() => form.setFieldValue('visibility', 'public')}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            </Group>
                        </Card>

                        <Card
                            padding="lg"
                            radius="md"
                            withBorder
                            style={{
                                border: form.values.visibility === 'private' ? '2px solid #2563EB' : '1px solid #E6E9EE',
                                background: form.values.visibility === 'private' ? '#EFF6FF' : '#FFFFFF',
                                cursor: 'pointer',
                            }}
                            onClick={() => form.setFieldValue('visibility', 'private')}
                        >
                            <Group>
                                <ThemeIcon size="xl" radius="md" variant="light" color="gray">
                                    <IconLock size={24} />
                                </ThemeIcon>
                                <Stack gap={2} style={{ flex: 1 }}>
                                    <Group gap="sm">
                                        <Text fw={600}>Private</Text>
                                        {form.values.visibility === 'private' && (
                                            <Badge size="sm" color="gray">Selected</Badge>
                                        )}
                                    </Group>
                                    <Text size="sm" c="dimmed">
                                        Only you can see this group. Perfect for personal organization or testing before making public.
                                    </Text>
                                </Stack>
                                <Checkbox
                                    checked={form.values.visibility === 'private'}
                                    onChange={() => form.setFieldValue('visibility', 'private')}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            </Group>
                        </Card>

                        <Alert
                            icon={<IconInfoCircle size={16} />}
                            color="blue"
                            variant="light"
                        >
                            You can change visibility settings at any time from the group settings.
                        </Alert>
                    </Stack>
                </Stepper.Step>

                {/* Step 4: Review & Create */}
                <Stepper.Step
                    label="Review"
                    description="Confirm details"
                    icon={<IconCheck size={18} />}
                >
                    <Stack gap="lg" mt="xl">
                        <Text fw={600} size="lg">Review Your Alert Group</Text>

                        <Paper p="md" radius="md" withBorder>
                            <Stack gap="md">
                                <Group justify="space-between" align="flex-start">
                                    <div>
                                        <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                            Group Name
                                        </Text>
                                        <Text fw={600} size="lg">{form.values.name || '-'}</Text>
                                    </div>
                                    <Badge color={CATEGORIES.find(c => c.value === form.values.category) ? 'blue' : 'gray'}>
                                        {form.values.category || 'No category'}
                                    </Badge>
                                </Group>

                                <Divider />

                                <div>
                                    <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                        Description
                                    </Text>
                                    <Text size="sm" mt={4}>{form.values.description || '-'}</Text>
                                </div>

                                <Divider />

                                <Group justify="space-between">
                                    <div>
                                        <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                            Tags
                                        </Text>
                                        <Group gap={6} mt={4}>
                                            {form.values.tags.length > 0 ? (
                                                form.values.tags.map((tag) => (
                                                    <Badge key={tag} size="sm" variant="outline" color="gray">
                                                        #{tag}
                                                    </Badge>
                                                ))
                                            ) : (
                                                <Text size="sm" c="dimmed">No tags</Text>
                                            )}
                                        </Group>
                                    </div>
                                    <div>
                                        <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                            Alert Type
                                        </Text>
                                        <Group gap={6} mt={4}>
                                            <Badge color="blue" variant="light">
                                                {ALERT_TYPES.find((t) => t.value === form.values.alert_type)?.label || form.values.alert_type}
                                            </Badge>
                                        </Group>
                                    </div>
                                    <div>
                                        <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                            Visibility
                                        </Text>
                                        <Group gap={6} mt={4}>
                                            {form.values.visibility === 'public' ? (
                                                <Badge
                                                    leftSection={<IconWorld size={12} />}
                                                    color="blue"
                                                >
                                                    Public
                                                </Badge>
                                            ) : (
                                                <Badge
                                                    leftSection={<IconLock size={12} />}
                                                    color="gray"
                                                >
                                                    Private
                                                </Badge>
                                            )}
                                        </Group>
                                    </div>
                                </Group>

                                <Divider />

                                <div>
                                    <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                                        Templates ({form.values.selectedTemplates.length})
                                    </Text>
                                    {form.values.selectedTemplates.length > 0 ? (
                                        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="xs" mt={4}>
                                            {form.values.selectedTemplates.map((templateId) => {
                                                const template = templates.find(t => t.id === templateId)
                                                return template ? (
                                                    <Card key={templateId} padding="xs" radius="sm" withBorder>
                                                        <Group gap="xs">
                                                            <IconBell size={14} color="#64748B" />
                                                            <Text size="xs" fw={500}>{template.name}</Text>
                                                        </Group>
                                                    </Card>
                                                ) : null
                                            })}
                                        </SimpleGrid>
                                    ) : (
                                        <Text size="sm" c="dimmed" mt={4}>
                                            No templates selected - you can add them later
                                        </Text>
                                    )}
                                </div>
                            </Stack>
                        </Paper>

                        <Alert
                            icon={<IconCheck size={16} />}
                            color="green"
                            variant="light"
                        >
                            Everything looks good! Click "Create Group" to finish.
                        </Alert>
                    </Stack>
                </Stepper.Step>

                <Stepper.Completed>
                    <Center h={200}>
                        <Stack align="center">
                            <ThemeIcon size="xl" radius="xl" color="green">
                                <IconCheck size={24} />
                            </ThemeIcon>
                            <Text fw={600}>Alert Group Created!</Text>
                            <Text size="sm" c="dimmed">
                                Your group is now available for subscription
                            </Text>
                        </Stack>
                    </Center>
                </Stepper.Completed>
            </Stepper>

            <Divider my="xl" />

            {/* Navigation Buttons */}
            <Group justify="space-between">
                <Button
                    variant="light"
                    color="gray"
                    onClick={handleClose}
                >
                    Cancel
                </Button>

                <Group gap="sm">
                    {active > 0 && active < 4 && (
                        <Button
                            variant="light"
                            leftSection={<IconChevronLeft size={16} />}
                            onClick={prevStep}
                        >
                            Back
                        </Button>
                    )}

                    {active < 3 ? (
                        <Button
                            rightSection={<IconChevronRight size={16} />}
                            onClick={nextStep}
                            style={{ backgroundColor: '#2563EB' }}
                        >
                            Next
                        </Button>
                    ) : active === 3 ? (
                        <Button
                            leftSection={<IconCheck size={16} />}
                            onClick={handleSubmit}
                            loading={isSubmitting}
                            style={{ backgroundColor: '#10B981' }}
                        >
                            Create Group
                        </Button>
                    ) : null}
                </Group>
            </Group>
        </Modal>
    )
}
