/**
 * Teams API Service
 *
 * API calls for team management.
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS } from '../config/api'

export interface TeamSummary {
  id: string
  name: string
  slug: string
  description?: string | null
  role: 'owner' | 'admin' | 'member' | 'viewer'
  member_count: number
  max_members: number
  created_at: string
}

export interface TeamMemberRecord {
  id: string
  name: string
  email: string
  role: 'owner' | 'admin' | 'member' | 'viewer'
  status: 'active' | 'pending'
  joined_at: string
  last_active_at?: string | null
}

class TeamsApiService {
  async getTeams(): Promise<TeamSummary[]> {
    const response = await httpClient.get<{ teams: TeamSummary[] }>(
      API_ENDPOINTS.TEAMS.LIST
    )
    return response.data.teams
  }

  async getMembers(teamId: string): Promise<TeamMemberRecord[]> {
    const response = await httpClient.get<{ members: TeamMemberRecord[] }>(
      API_ENDPOINTS.TEAMS.MEMBERS(teamId)
    )
    return response.data.members
  }

  async inviteMember(teamId: string, payload: { email: string; role: TeamMemberRecord['role'] }) {
    const response = await httpClient.post<{ member: TeamMemberRecord }>(
      API_ENDPOINTS.TEAMS.INVITE(teamId),
      payload
    )
    return response.data.member
  }

  async updateMemberRole(teamId: string, memberId: string, role: TeamMemberRecord['role']) {
    const response = await httpClient.patch<TeamMemberRecord>(
      API_ENDPOINTS.TEAMS.MEMBER_DETAIL(teamId, memberId),
      { role }
    )
    return response.data
  }

  async removeMember(teamId: string, memberId: string): Promise<void> {
    await httpClient.delete(API_ENDPOINTS.TEAMS.MEMBER_DETAIL(teamId, memberId))
  }

  async resendInvite(teamId: string, memberId: string): Promise<void> {
    await httpClient.post(API_ENDPOINTS.TEAMS.MEMBER_RESEND_INVITE(teamId, memberId), {})
  }
}

export const teamsApiService = new TeamsApiService()
export default teamsApiService
