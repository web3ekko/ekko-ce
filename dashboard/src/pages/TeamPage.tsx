/**
 * Team Page - Improved Version
 *
 * Team management and collaboration features with card-based layout
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Container,
  Title,
  Button,
  Grid,
  Card,
  Text,
  Group,
  Stack,
  Badge,
  TextInput,
  Select,
  Tabs,
  Alert,
  SimpleGrid,
  Center,
  Loader,
} from '@mantine/core'
import {
  IconPlus,
  IconSearch,
  IconUsers,
  IconShield,
  IconAlertCircle,
  IconCheck,
} from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { TeamMemberCard, type TeamMember } from '../components/team/TeamMemberCard'
import teamsApiService, { type TeamMemberRecord, type TeamSummary } from '../services/teams-api'
import { InviteMemberModal } from '../components/team/InviteMemberModal'

const formatRelativeTime = (timestamp?: string | null) => {
  if (!timestamp) return 'Never'
  const now = Date.now()
  const value = new Date(timestamp).getTime()
  const diff = now - value

  if (diff < 60 * 1000) return 'Just now'
  if (diff < 60 * 60 * 1000) return `${Math.floor(diff / (60 * 1000))}m ago`
  if (diff < 24 * 60 * 60 * 1000) return `${Math.floor(diff / (60 * 60 * 1000))}h ago`
  return new Date(timestamp).toLocaleDateString()
}

const mapMember = (member: TeamMemberRecord): TeamMember => ({
  id: member.id,
  name: member.name || member.email,
  email: member.email,
  role: member.role,
  status: member.status,
  joinedAt: member.joined_at,
  lastActive: formatRelativeTime(member.last_active_at),
})

export function TeamPage() {
  const [inviteOpened, { open: openInvite, close: closeInvite }] = useDisclosure(false)
  const [activeTab, setActiveTab] = useState<string | null>('members')
  const [searchQuery, setSearchQuery] = useState('')
  const [teams, setTeams] = useState<TeamSummary[]>([])
  const [members, setMembers] = useState<TeamMemberRecord[]>([])
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const selectedTeam = teams.find((team) => team.id === selectedTeamId) || null

  const loadTeams = async () => {
    setIsLoading(true)
    try {
      const teamList = await teamsApiService.getTeams()
      setTeams(teamList)
      if (!selectedTeamId && teamList.length > 0) {
        setSelectedTeamId(teamList[0].id)
      }
    } catch (error) {
      console.error('Failed to load teams:', error)
      notifications.show({
        title: 'Error',
        message: 'Failed to load teams',
        color: 'red',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const loadMembers = async (teamId: string) => {
    setIsLoading(true)
    try {
      const teamMembers = await teamsApiService.getMembers(teamId)
      setMembers(teamMembers)
    } catch (error) {
      console.error('Failed to load team members:', error)
      notifications.show({
        title: 'Error',
        message: 'Failed to load team members',
        color: 'red',
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadTeams()
  }, [])

  useEffect(() => {
    if (selectedTeamId) {
      loadMembers(selectedTeamId)
    } else {
      setMembers([])
    }
  }, [selectedTeamId])

  const handleInviteMember = async (formData: { email: string; role: TeamMember['role'] }) => {
    if (!selectedTeamId) {
      return
    }

    try {
      await teamsApiService.inviteMember(selectedTeamId, formData)
      notifications.show({
        title: 'Invitation Sent',
        message: `Invitation sent to ${formData.email}`,
        color: 'green',
        icon: <IconCheck size={16} />,
      })
      closeInvite()
      await loadMembers(selectedTeamId)
    } catch (error) {
      console.error('Failed to invite member:', error)
      notifications.show({
        title: 'Invite failed',
        message: 'Unable to invite team member. Ensure the user exists and try again.',
        color: 'red',
      })
    }
  }

  const handleRemoveMember = async (id: string) => {
    if (!selectedTeamId) return
    if (!confirm('Are you sure you want to remove this team member?')) return

    try {
      await teamsApiService.removeMember(selectedTeamId, id)
      notifications.show({
        title: 'Member Removed',
        message: 'Team member has been removed successfully',
        color: 'orange',
      })
      await loadMembers(selectedTeamId)
    } catch (error) {
      console.error('Failed to remove member:', error)
      notifications.show({
        title: 'Remove failed',
        message: 'Unable to remove team member',
        color: 'red',
      })
    }
  }

  const handleResendInvite = async (email: string) => {
    if (!selectedTeamId) return
    const member = members.find((item) => item.email === email)
    if (!member) return

    try {
      await teamsApiService.resendInvite(selectedTeamId, member.id)
      notifications.show({
        title: 'Invite Resent',
        message: `Invitation resent to ${email}`,
        color: 'blue',
        icon: <IconCheck size={16} />,
      })
    } catch (error) {
      console.error('Failed to resend invite:', error)
      notifications.show({
        title: 'Resend failed',
        message: 'Unable to resend invite',
        color: 'red',
      })
    }
  }

  const handleUpdateMember = async (member: TeamMember) => {
    if (!selectedTeamId) return
    try {
      await teamsApiService.updateMemberRole(selectedTeamId, member.id, member.role)
      notifications.show({
        title: 'Role Updated',
        message: `${member.name}'s role updated`,
        color: 'green',
      })
      await loadMembers(selectedTeamId)
    } catch (error) {
      console.error('Failed to update member role:', error)
      notifications.show({
        title: 'Update failed',
        message: 'Unable to update member role',
        color: 'red',
      })
    }
  }

  const filteredMembers = useMemo(() => {
    const formatted = members.map(mapMember)
    return formatted.filter((member) =>
      member.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      member.email.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [members, searchQuery])

  const totalMembers = members.length
  const activeMembers = members.filter((member) => member.status === 'active').length
  const adminCount = members.filter((member) => ['owner', 'admin'].includes(member.role)).length

  if (isLoading && teams.length === 0) {
    return (
      <Container size="xl" py="xl">
        <Center h={240}>
          <Stack align="center" gap="sm">
            <Loader size="lg" />
            <Text c="#64748B">Loading team data...</Text>
          </Stack>
        </Center>
      </Container>
    )
  }

  return (
    <Container size="xl" py="xl">
      <Stack gap="xl">
        {/* Header */}
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={1} c="#0F172A">Team</Title>
            <Text c="#475569" mt="xs">
              Manage your team members and permissions
            </Text>
          </div>
          <Group gap="md">
            {teams.length > 1 && (
              <Select
                data={teams.map((team) => ({ value: team.id, label: team.name }))}
                value={selectedTeamId}
                onChange={(value) => setSelectedTeamId(value)}
                placeholder="Select team"
              />
            )}
            <Button
              leftSection={<IconPlus size={16} />}
              style={{ backgroundColor: '#2563EB' }}
              onClick={openInvite}
              disabled={!selectedTeamId}
            >
              Invite Member
            </Button>
          </Group>
        </Group>

        {teams.length === 0 ? (
          <Card withBorder radius="md">
            <Stack align="center" gap="sm" py="xl">
              <IconUsers size={32} color="#94A3B8" />
              <Text fw={600}>No teams found</Text>
              <Text size="sm" c="dimmed">Create a team to start collaborating.</Text>
            </Stack>
          </Card>
        ) : (
          <>
            {/* Stats Overview */}
            <Grid>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Card padding="md" radius="md" withBorder>
                  <Group gap="xs">
                    <IconUsers size={20} color="#2563EB" />
                    <div>
                      <Text size="sm" c="#475569">Total Members</Text>
                      <Text size="xl" fw={700} c="#0F172A">{totalMembers}</Text>
                    </div>
                  </Group>
                </Card>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Card padding="md" radius="md" withBorder>
                  <Group gap="xs">
                    <IconCheck size={20} color="#10B981" />
                    <div>
                      <Text size="sm" c="#475569">Active Members</Text>
                      <Text size="xl" fw={700} c="#0F172A">
                        {activeMembers}
                      </Text>
                    </div>
                  </Group>
                </Card>
              </Grid.Col>
              <Grid.Col span={{ base: 12, md: 4 }}>
                <Card padding="md" radius="md" withBorder>
                  <Group gap="xs">
                    <IconShield size={20} color="#F59E0B" />
                    <div>
                      <Text size="sm" c="#475569">Admins</Text>
                      <Text size="xl" fw={700} c="#0F172A">
                        {adminCount}
                      </Text>
                    </div>
                  </Group>
                </Card>
              </Grid.Col>
            </Grid>

            {/* Main Content */}
            <Tabs value={activeTab} onChange={setActiveTab}>
              <Tabs.List>
                <Tabs.Tab value="members" leftSection={<IconUsers size={16} />}>
                  Members
                </Tabs.Tab>
                <Tabs.Tab value="permissions" leftSection={<IconShield size={16} />}>
                  Permissions
                </Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="members" pt="xl">
                <Stack gap="md">
                  <Group justify="space-between">
                    <TextInput
                      placeholder="Search members..."
                      leftSection={<IconSearch size={16} />}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{ flex: 1, maxWidth: 400 }}
                    />
                    {selectedTeam && (
                      <Alert
                        icon={<IconAlertCircle size={16} />}
                        title="Team Limit"
                        color="blue"
                        variant="light"
                        py="xs"
                      >
                        <Text size="sm">
                          You're using {totalMembers} of {selectedTeam.max_members} team member slots.
                        </Text>
                      </Alert>
                    )}
                  </Group>

                  {isLoading ? (
                    <Center py="xl">
                      <Loader size="sm" />
                    </Center>
                  ) : (
                    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
                      {filteredMembers.map((member) => (
                        <TeamMemberCard
                          key={member.id}
                          member={member}
                          onEdit={handleUpdateMember}
                          onRemove={handleRemoveMember}
                          onResendInvite={handleResendInvite}
                        />
                      ))}
                    </SimpleGrid>
                  )}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="permissions" pt="xl">
                <Card withBorder radius="md" padding="xl">
                  <Stack gap="sm">
                    <Title order={4}>Permissions</Title>
                    <Text size="sm" c="dimmed">
                      Role-based permissions are managed by your organization admins.
                    </Text>
                  </Stack>
                </Card>
              </Tabs.Panel>
            </Tabs>
          </>
        )}
      </Stack>

      <InviteMemberModal
        opened={inviteOpened}
        onClose={closeInvite}
        onSubmit={handleInviteMember}
      />
    </Container>
  )
}
