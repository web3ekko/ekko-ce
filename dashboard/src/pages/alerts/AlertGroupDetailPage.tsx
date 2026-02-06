import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Container,
  Divider,
  Group,
  Loader,
  Modal,
  MultiSelect,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconAlertCircle,
  IconArrowLeft,
  IconCheck,
  IconEdit,
  IconLock,
  IconPlus,
  IconTrash,
  IconWorld,
} from '@tabler/icons-react'
import type { GenericGroup, AlertGroupTemplatesResponse } from '../../services/groups-api'
import groupsApiService from '../../services/groups-api'
import { useAuthStore } from '../../store/auth'
import { API_ENDPOINTS } from '../../config/api'
import { httpClient } from '../../services/http-client'

type AlertGroupAlertType = 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft'

type TemplateVariable = {
  id?: string
  name?: string
  type?: string
  required?: boolean
}

type ApiAlertTemplate = {
  id: string
  name: string
  description: string
  event_type: string
  template_type: string
  alert_type: string
  spec?: { variables?: TemplateVariable[] } | null
  variables?: TemplateVariable[] | null
  is_verified: boolean
}

function getVariableId(variable: TemplateVariable): string | null {
  const raw = variable.id ?? variable.name
  if (!raw || typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed.length ? trimmed : null
}

function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false
  for (const v of a) {
    if (!b.has(v)) return false
  }
  return true
}

function buildTargetingVariableIds(alertType: AlertGroupAlertType): Set<string> {
  const base = new Set([
    'network',
    'networks',
    'network_key',
    'chain',
    'chains',
    'chain_id',
    'subnet',
    'network_id',
  ])

  if (alertType === 'wallet') {
    ;[
      'wallet',
      'wallet_key',
      'wallet_address',
      'address',
      'wallet_group',
      'wallet_group_id',
      'wallets',
      'addresses',
      'target_wallet',
      'target_key',
      'target',
      'targets',
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
      'token',
      'token_key',
      'token_address',
      'token_contract',
      'token_contract_address',
      'token_id',
      'asset',
      'asset_address',
      'tokens',
    ].forEach((id) => base.add(id))
    return base
  }

  if (alertType === 'contract' || alertType === 'nft') {
    ;[
      'contract',
      'contract_key',
      'contract_address',
      'contract_addresses',
      'contracts',
      'protocol',
      'protocol_address',
      'protocol_addresses',
      'protocol_contract',
      'collection',
      'collection_key',
      'collection_address',
      'collection_addresses',
      'nft_contract',
      'nft_contract_address',
      'token_id',
    ].forEach((id) => base.add(id))
    return base
  }

  return base
}

function getTemplateTargetAlertType(template: ApiAlertTemplate): AlertGroupAlertType {
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

function extractTemplateVariables(template: ApiAlertTemplate): TemplateVariable[] {
  const specVars = template.spec?.variables
  if (Array.isArray(specVars)) return specVars
  if (Array.isArray(template.variables)) return template.variables
  return []
}

function getTemplateRequiredParamIds(template: ApiAlertTemplate): Set<string> {
  const targetAlertType = getTemplateTargetAlertType(template)
  const targetingIds = buildTargetingVariableIds(targetAlertType)

  const requiredIds = new Set<string>()
  for (const variable of extractTemplateVariables(template)) {
    if (!variable?.required) continue
    const id = getVariableId(variable)
    if (!id) continue
    if (targetingIds.has(id.toLowerCase())) continue
    requiredIds.add(id.toLowerCase())
  }
  return requiredIds
}

function getGroupVisibility(group: GenericGroup | null): 'private' | 'public' {
  const visibility = group?.settings?.visibility
  return visibility === 'public' ? 'public' : 'private'
}

function getGroupCategory(group: GenericGroup | null): string {
  const category = group?.settings?.category
  return typeof category === 'string' && category.trim().length ? category : 'Other'
}

function getGroupTags(group: GenericGroup | null): string[] {
  const tags = group?.settings?.tags
  if (!Array.isArray(tags)) return []
  return tags.map((t) => String(t)).map((t) => t.trim()).filter(Boolean)
}

export function AlertGroupDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [group, setGroup] = useState<GenericGroup | null>(null)
  const [templatesResponse, setTemplatesResponse] = useState<AlertGroupTemplatesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editOpened, editHandlers] = useDisclosure(false)
  const [addTemplateOpened, addTemplateHandlers] = useDisclosure(false)
  const [isSaving, setIsSaving] = useState(false)

  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editCategory, setEditCategory] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])
  const [editVisibility, setEditVisibility] = useState<'private' | 'public'>('private')

  const [availableTemplates, setAvailableTemplates] = useState<ApiAlertTemplate[]>([])
  const [templateSearch, setTemplateSearch] = useState('')
  const [isLoadingAvailableTemplates, setIsLoadingAvailableTemplates] = useState(false)

  const groupAlertType = useMemo<AlertGroupAlertType>(() => {
    const raw = (templatesResponse?.alert_type ||
      (typeof group?.settings?.alert_type === 'string' ? (group.settings.alert_type as string) : 'wallet')) as string
    const normalized = raw.toLowerCase()
    if (
      normalized === 'wallet' ||
      normalized === 'network' ||
      normalized === 'protocol' ||
      normalized === 'token' ||
      normalized === 'contract' ||
      normalized === 'nft'
    ) {
      return normalized as AlertGroupAlertType
    }
    return 'wallet'
  }, [group?.settings, templatesResponse?.alert_type])

  const isOwner = !!group && !!user?.email && group.owner_email === user.email

  const existingTemplateIds = useMemo(() => {
    const ids = new Set<string>()
    for (const t of templatesResponse?.templates || []) {
      ids.add(t.id)
    }
    return ids
  }, [templatesResponse?.templates])

  const baselineTemplateType = useMemo(() => {
    const first = templatesResponse?.templates?.[0]
    return first?.template_type?.toLowerCase() || null
  }, [templatesResponse?.templates])

  const baselineRequiredIds = useMemo(() => {
    const first = templatesResponse?.templates?.[0]
    if (!first) return null
    const targetingIds = buildTargetingVariableIds(groupAlertType)
    const required = new Set<string>()
    const vars = (first.variables || []) as TemplateVariable[]
    for (const v of vars) {
      if (!v?.required) continue
      const id = getVariableId(v)
      if (!id) continue
      if (targetingIds.has(id.toLowerCase())) continue
      required.add(id.toLowerCase())
    }
    return required
  }, [groupAlertType, templatesResponse?.templates])

  const compatibleAvailableTemplates = useMemo(() => {
    const eligible = availableTemplates.filter((t) => getTemplateTargetAlertType(t) === groupAlertType)

    const search = templateSearch.trim().toLowerCase()
    const searched = search.length
      ? eligible.filter(
          (t) =>
            t.name.toLowerCase().includes(search) ||
            t.description.toLowerCase().includes(search) ||
            t.event_type.toLowerCase().includes(search) ||
            t.template_type.toLowerCase().includes(search)
        )
      : eligible

    return searched.map((t) => {
      let disabledReason: string | null = null
      if (existingTemplateIds.has(t.id)) {
        disabledReason = 'Already in group'
      } else if (baselineTemplateType && t.template_type.toLowerCase() !== baselineTemplateType) {
        disabledReason = `Template type mismatch (${t.template_type} ≠ ${baselineTemplateType})`
      } else if (baselineRequiredIds && !setsEqual(getTemplateRequiredParamIds(t), baselineRequiredIds)) {
        disabledReason = 'Required settings mismatch'
      }
      return { template: t, disabledReason }
    })
  }, [availableTemplates, baselineRequiredIds, baselineTemplateType, existingTemplateIds, groupAlertType, templateSearch])

  const load = async (groupId: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const [loadedGroup, loadedTemplates] = await Promise.all([
        groupsApiService.getGroup(groupId),
        groupsApiService.getAlertGroupTemplates(groupId),
      ])
      setGroup(loadedGroup)
      setTemplatesResponse(loadedTemplates)
    } catch (err) {
      console.error('Failed to load alert group:', err)
      setError('Failed to load alert group')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!id) return
    load(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    if (!group) return
    setEditName(group.name)
    setEditDescription(group.description)
    setEditCategory(getGroupCategory(group))
    setEditTags(getGroupTags(group))
    setEditVisibility(getGroupVisibility(group))
  }, [group])

  const loadAvailableTemplates = async () => {
    setIsLoadingAvailableTemplates(true)
    try {
      const response = await httpClient.get<any>(API_ENDPOINTS.ALERT_TEMPLATES.LIST)
      const payload = response.data
      const results: ApiAlertTemplate[] = Array.isArray(payload) ? payload : (payload?.results || [])
      setAvailableTemplates(results)
    } catch (err) {
      console.error('Failed to load templates:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to load templates',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsLoadingAvailableTemplates(false)
    }
  }

  const handleOpenAddTemplates = async () => {
    setTemplateSearch('')
    addTemplateHandlers.open()
    if (!availableTemplates.length) {
      await loadAvailableTemplates()
    }
  }

  const handleSaveEdits = async () => {
    if (!group) return
    setIsSaving(true)

    try {
      await groupsApiService.updateGroup(group.id, {
        name: editName,
        description: editDescription,
        settings: {
          ...(group.settings || {}),
          category: editCategory,
          tags: editTags,
          visibility: editVisibility,
        },
      })

      notifications.show({
        title: 'Saved',
        message: 'Group updated',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      editHandlers.close()
      await load(group.id)
    } catch (err) {
      console.error('Failed to update group:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to update group',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleRemoveTemplate = async (templateId: string) => {
    if (!group) return
    setIsSaving(true)
    try {
      await groupsApiService.removeMembers(group.id, {
        members: [{ member_key: `template:${templateId}` }],
      })
      await load(group.id)
      notifications.show({
        title: 'Removed',
        message: 'Template removed from group',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err) {
      console.error('Failed to remove template:', err)
      notifications.show({
        title: 'Error',
        message: 'Failed to remove template',
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleAddTemplate = async (templateId: string) => {
    if (!group) return
    setIsSaving(true)
    try {
      await groupsApiService.addMembers(group.id, {
        members: [{ member_key: `template:${templateId}` }],
      })
      await load(group.id)
      notifications.show({
        title: 'Added',
        message: 'Template added to group',
        color: 'green',
        icon: <IconCheck size={16} />,
      })
    } catch (err: any) {
      const backendMessage =
        (err?.response?.data?.members && Array.isArray(err.response.data.members) && err.response.data.members.join('\n')) ||
        err?.message ||
        'Failed to add template'
      console.error('Failed to add template:', err)
      notifications.show({
        title: 'Error',
        message: backendMessage,
        color: 'red',
        icon: <IconAlertCircle size={16} />,
      })
    } finally {
      setIsSaving(false)
    }
  }

  if (!id) {
    return (
      <Container size="lg" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} color="red">
          Missing alert group id
        </Alert>
      </Container>
    )
  }

  if (isLoading) {
    return (
      <Center h={320}>
        <Stack align="center" gap="sm">
          <Loader size="lg" />
          <Text c="dimmed">Loading alert group…</Text>
        </Stack>
      </Center>
    )
  }

  if (error || !group || !templatesResponse) {
    return (
      <Container size="lg" py="xl">
        <Alert icon={<IconAlertCircle size={16} />} color="red">
          {error || 'Alert group not found'}
        </Alert>
        <Button mt="md" variant="light" onClick={() => navigate('/dashboard/alerts/groups')}>
          Back to Alert Groups
        </Button>
      </Container>
    )
  }

  const visibility = getGroupVisibility(group)
  const category = getGroupCategory(group)
  const tags = getGroupTags(group)

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        <Group justify="space-between" align="flex-start">
          <div>
            <Button
              variant="subtle"
              leftSection={<IconArrowLeft size={16} />}
              onClick={() => navigate(-1)}
              mb="sm"
            >
              Back
            </Button>

            <Group gap="sm" align="center" mb={6}>
              <Text fw={800} size="xl" c="#0F172A">
                {group.name}
              </Text>
              <Badge variant="light" color="blue">
                {category}
              </Badge>
              <Badge variant="light" color="gray">
                {groupAlertType}
              </Badge>
              <Badge
                leftSection={visibility === 'public' ? <IconWorld size={12} /> : <IconLock size={12} />}
                color={visibility === 'public' ? 'blue' : 'gray'}
                variant="light"
              >
                {visibility}
              </Badge>
            </Group>

            <Text c="#475569">{group.description}</Text>

            {tags.length > 0 && (
              <Group gap={6} mt="sm">
                {tags.map((tag) => (
                  <Badge key={tag} size="sm" variant="outline" color="gray">
                    #{tag}
                  </Badge>
                ))}
              </Group>
            )}
          </div>

          <Group gap="sm">
            {isOwner && (
              <>
                <Button variant="light" leftSection={<IconEdit size={16} />} onClick={editHandlers.open}>
                  Edit
                </Button>
                <Button
                  leftSection={<IconPlus size={16} />}
                  style={{ backgroundColor: '#2563EB' }}
                  onClick={handleOpenAddTemplates}
                >
                  Add Template
                </Button>
              </>
            )}
          </Group>
        </Group>

        <Card withBorder radius="md" p="md">
          <Group justify="space-between" align="center" mb="sm">
            <Text fw={700} c="#0F172A">
              Templates
            </Text>
            <Badge variant="light" color="gray">
              {templatesResponse.templates.length}
            </Badge>
          </Group>

          {templatesResponse.templates.length === 0 ? (
            <Text c="dimmed" size="sm">
              No templates in this group yet.
            </Text>
          ) : (
            <Table verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Template</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Alert Type</Table.Th>
                  {isOwner && <Table.Th />}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {templatesResponse.templates.map((template) => (
                  <Table.Tr key={template.id}>
                    <Table.Td>
                      <Stack gap={2}>
                        <Text fw={600} size="sm">
                          {template.name}
                        </Text>
                        <Text size="xs" c="dimmed" lineClamp={2}>
                          {template.description}
                        </Text>
                      </Stack>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="sm" variant="light" color="blue">
                        {template.template_type}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge size="sm" variant="light" color="gray">
                        {template.alert_type || '–'}
                      </Badge>
                    </Table.Td>
                    {isOwner && (
                      <Table.Td>
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          leftSection={<IconTrash size={14} />}
                          loading={isSaving}
                          onClick={() => handleRemoveTemplate(template.id)}
                        >
                          Remove
                        </Button>
                      </Table.Td>
                    )}
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Card>
      </Stack>

      {/* Edit modal */}
      <Modal opened={editOpened} onClose={editHandlers.close} title="Edit Alert Group" size="lg">
        <Stack gap="md">
          <TextInput label="Name" value={editName} onChange={(e) => setEditName(e.currentTarget.value)} />
          <Textarea
            label="Description"
            minRows={3}
            value={editDescription}
            onChange={(e) => setEditDescription(e.currentTarget.value)}
          />

          <Select
            label="Category"
            data={[
              { value: 'DeFi', label: 'DeFi' },
              { value: 'NFT', label: 'NFT' },
              { value: 'Security', label: 'Security' },
              { value: 'Network', label: 'Network' },
              { value: 'Trading', label: 'Trading' },
              { value: 'Development', label: 'Development' },
              { value: 'Analytics', label: 'Analytics' },
              { value: 'Other', label: 'Other' },
            ]}
            value={editCategory}
            onChange={(value) => setEditCategory(value || 'Other')}
          />

          <MultiSelect
            label="Tags"
            data={Array.from(new Set([...tags, ...editTags]))}
            value={editTags}
            onChange={setEditTags}
            searchable
            creatable
            getCreateLabel={(query) => `+ Create "${query}"`}
          />

          <Select
            label="Visibility"
            data={[
              { value: 'private', label: 'Private' },
              { value: 'public', label: 'Public' },
            ]}
            value={editVisibility}
            onChange={(value) => setEditVisibility((value as any) || 'private')}
          />

          <Divider />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={editHandlers.close}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdits} loading={isSaving} style={{ backgroundColor: '#2563EB' }}>
              Save
            </Button>
          </Group>
        </Stack>
      </Modal>

      {/* Add template modal */}
      <Modal opened={addTemplateOpened} onClose={addTemplateHandlers.close} title="Add Templates" size="xl">
        <Stack gap="md">
          <TextInput
            placeholder="Search templates…"
            value={templateSearch}
            onChange={(e) => setTemplateSearch(e.currentTarget.value)}
          />

          {isLoadingAvailableTemplates ? (
            <Center h={200}>
              <Loader size="lg" />
            </Center>
          ) : (
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
              {compatibleAvailableTemplates.map(({ template, disabledReason }) => {
                const disabled = !!disabledReason
                return (
                  <Card
                    key={template.id}
                    withBorder
                    radius="md"
                    p="md"
                    style={{
                      opacity: disabled ? 0.55 : 1,
                    }}
                  >
                    <Group justify="space-between" align="flex-start">
                      <Stack gap={4} style={{ flex: 1 }}>
                        <Text fw={700} size="sm" c="#0F172A" lineClamp={1}>
                          {template.name}
                        </Text>
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
                        {disabledReason && (
                          <Text size="xs" c="dimmed">
                            {disabledReason}
                          </Text>
                        )}
                      </Stack>
                      <Button
                        size="xs"
                        leftSection={<IconPlus size={14} />}
                        disabled={disabled || !isOwner}
                        loading={isSaving}
                        onClick={() => handleAddTemplate(template.id)}
                      >
                        Add
                      </Button>
                    </Group>
                  </Card>
                )
              })}
            </SimpleGrid>
          )}

          {!isOwner && (
            <Alert icon={<IconLock size={16} />} color="yellow">
              Only the group owner can add templates.
            </Alert>
          )}

          <Divider />
          <Group justify="flex-end">
            <Button variant="subtle" onClick={addTemplateHandlers.close}>
              Close
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Container>
  )
}
