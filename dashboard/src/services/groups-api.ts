/**
 * Groups API Service
 *
 * Unified API service for GenericGroup management (wallets, alerts, networks, tokens)
 */

import { httpClient } from './http-client'
import { API_ENDPOINTS, type PaginatedResponse } from '../config/api'

// Group Types enum - matches backend GroupType
export enum GroupType {
  WALLET = 'wallet',
  ALERT = 'alert',
  USER = 'user',
  NETWORK = 'network',
  PROTOCOL = 'protocol',
  TOKEN = 'token',
  CONTRACT = 'contract',
  NFT = 'nft',
}

// Generic Group interface - matches backend GenericGroupSerializer
export interface GenericGroup {
  id: string
  group_type: GroupType
  group_type_display: string
  name: string
  description: string
  owner: string
  owner_email: string
  settings: Record<string, unknown>
  member_data: {
    members: Record<string, GroupMemberMetadata>
  }
  member_count: number
  member_keys: string[]
  created_at: string
  updated_at: string
}

// Group member metadata stored in JSONB
export interface GroupMemberMetadata {
  added_by: string
  added_at: string
  label?: string
  tags?: string[]
  metadata?: Record<string, unknown>
}

// Group member with key for list display
export interface GroupMember {
  member_key: string
  added_by: string
  added_at: string
  label?: string
  tags?: string[]
  metadata?: Record<string, unknown>
}

// Group subscription - links alert groups to target groups
export interface GroupSubscription {
  id: string
  alert_group: string
  alert_group_name: string
  target_group: string | null
  target_group_name: string | null
  target_group_type: GroupType | null
  target_key: string | null
  owner: string
  settings: Record<string, unknown>
  is_active: boolean
  created_at: string
  updated_at: string
}

// Request types
export interface CreateGroupRequest {
  group_type: GroupType
  name: string
  description?: string
  settings?: Record<string, unknown>
  initial_members?: Array<{
    member_key: string
    label?: string
    tags?: string[]
    metadata?: Record<string, unknown>
  }>
}

export interface UpdateGroupRequest {
  name?: string
  description?: string
  settings?: Record<string, unknown>
}

export interface AddMembersRequest {
  members: Array<{
    member_key: string
    label?: string
    tags?: string[]
    metadata?: Record<string, unknown>
  }>
}

export interface UpdateMembersRequest {
  members: Array<{
    member_key: string
    label?: string
    tags?: string[]
    metadata?: Record<string, unknown>
  }>
}

export interface RemoveMembersRequest {
  members: Array<{ member_key: string }>
}

export interface CreateSubscriptionRequest {
  alert_group: string
  target_group?: string | null
  target_key?: string | null
  settings?: Record<string, unknown>
}

export interface UpdateSubscriptionRequest {
  settings?: Record<string, unknown>
  is_active?: boolean
}

// Response shapes for member operations
export interface AddMembersResponse {
  added: number
  already_exists: string[]
  total_members: number
}

export interface UpdateMembersResponse {
  updated: number
  not_found: string[]
  total_members: number
}

export interface RemoveMembersResponse {
  removed: number
  not_found: string[]
  total_members: number
}

export interface GroupMembersResponse {
  group_id: string
  group_name: string
  member_count: number
  members: Record<string, GroupMemberMetadata>
}

// List params
export interface GroupsListParams {
  page?: number
  page_size?: number
  group_type?: GroupType
  search?: string
  ordering?: string
}

export interface GroupsSplitResponse {
  my_groups: PaginatedResponse<GenericGroup>
  public_groups: PaginatedResponse<GenericGroup>
}

export interface SubscriptionsListParams {
  page?: number
  page_size?: number
  alert_group_id?: string
  target_group_id?: string
  is_active?: boolean
}

// Group summary by type
export interface GroupsSummary {
  [key: string]: {
    count: number
    total_members: number
  }
}

// Notification routing choices for provider-managed groups
export type NotificationRoutingChoice = 'callback_only' | 'user_channels' | 'both'

// UserWalletGroup - Provider-managed wallet group for a user
export interface UserWalletGroup {
  id: string
  user: string
  user_email?: string
  wallet_group: string
  wallet_group_name: string
  provider: string
  provider_name: string
  callback?: {
    id: string
    channel_type: string
    label: string
    config: {
      url: string
      method?: string
      headers?: Record<string, string>
    }
  }
  wallet_keys: string[]
  auto_subscribe_alerts: boolean
  notification_routing: NotificationRoutingChoice
  access_control: {
    editors?: {
      users: string[]
      api_keys: string[]
    }
  }
  is_active: boolean
  created_at: string
  updated_at: string
}

// DefaultNetworkAlert - Fallback alerts per chain/subnet
export interface DefaultNetworkAlert {
  id: string
  chain: string
  chain_name: string
  chain_symbol?: string
  subnet: string
  alert_template: string
  alert_template_name?: string
  enabled: boolean
  settings: Record<string, unknown>
  created_at: string
  updated_at: string
}

// Request types for UserWalletGroup
export interface UpdateUserWalletGroupRequest {
  notification_routing?: NotificationRoutingChoice
  auto_subscribe_alerts?: boolean
  is_active?: boolean
  callback?: string | null
  access_control?: Record<string, any>
}

export interface CreateUserWalletGroupRequest {
  wallet_group: string
  wallet_keys?: string[]
  provider?: string
  user?: string
  callback?: string | null
  notification_routing?: NotificationRoutingChoice
  auto_subscribe_alerts?: boolean
  access_control?: Record<string, any>
  is_active?: boolean
}

export interface UserWalletGroupWalletsResponse {
  id: string
  added?: string[]
  removed?: string[]
  duplicates?: string[]
  not_found?: string[]
  total_wallets: number
}

export interface UserWalletGroupImportResponse {
  id: string
  merge_mode: 'append' | 'replace'
  added: string[]
  duplicates: string[]
  invalid_rows: number[]
  errors: { row_number: number; error: string }[]
  total_wallets: number
}

// Accounts (system group) requests/responses
export interface AccountsAddWalletRequest {
  member_key: string
  label?: string
  owner_verified?: boolean
}

export interface AccountsAddWalletResponse {
  group_id: string
  created: boolean
  added: boolean
  wallet_id: string
  wallet_created: boolean
  total_members: number
}

export interface AccountsAddWalletsRequest {
  wallets: AccountsAddWalletRequest[]
}

export interface AccountsAddWalletsError {
  row_number: number
  member_key: string
  errors: Record<string, unknown>
}

export interface AccountsAddWalletsResponse {
  group_id: string
  created: boolean
  added: number
  already_exists: string[]
  wallet_rows_created: number
  errors: AccountsAddWalletsError[]
  total_members: number
}

// AlertGroup template discovery
export interface AlertGroupTemplate {
  id: string
  name: string
  description: string
  template_type: string
  alert_type: string
  variables: Array<Record<string, unknown>>
}

export interface AlertGroupTemplatesResponse {
  alert_group_id: string
  alert_group_name: string
  alert_type: string
  templates: AlertGroupTemplate[]
}

class GroupsApiService {
  // ============================================
  // GROUPS CRUD
  // ============================================

  // List groups with optional filtering
  async getGroups(params: GroupsListParams = {}): Promise<PaginatedResponse<GenericGroup>> {
    try {
      const response = await httpClient.get<PaginatedResponse<GenericGroup>>(
        API_ENDPOINTS.GROUPS.LIST,
        params
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get groups failed:', error)
      throw error
    }
  }

  // List groups split into my_groups and public_groups
  async getGroupsSplit(params: GroupsListParams = {}): Promise<GroupsSplitResponse> {
    try {
      const response = await httpClient.get<GroupsSplitResponse>(API_ENDPOINTS.GROUPS.LIST, params)
      return response.data
    } catch (error: unknown) {
      console.error('Get groups (split) failed:', error)
      throw error
    }
  }

  // List public groups (discoverable/subscribable)
  async getPublicGroups(params: GroupsListParams = {}): Promise<PaginatedResponse<GenericGroup>> {
    try {
      const response = await httpClient.get<PaginatedResponse<GenericGroup> | GenericGroup[]>(
        API_ENDPOINTS.GROUPS.PUBLIC,
        params
      )

      // Depending on pagination settings, this endpoint may return either:
      // - PaginatedResponse<GenericGroup>
      // - GenericGroup[]
      if (Array.isArray(response.data)) {
        return {
          count: response.data.length,
          next: null,
          previous: null,
          results: response.data,
        }
      }

      return response.data
    } catch (error: unknown) {
      console.error('Get public groups failed:', error)
      throw error
    }
  }

  // Get groups by type
  async getGroupsByType(
    groupType: GroupType,
    params: Omit<GroupsListParams, 'group_type'> = {}
  ): Promise<PaginatedResponse<GenericGroup>> {
    try {
      // Backend by_type endpoint returns a plain array, not paginated
      const response = await httpClient.get<GenericGroup[]>(
        API_ENDPOINTS.GROUPS.BY_TYPE,
        { ...params, type: groupType }
      )
      // Wrap in paginated response format for consistency
      const groups = response.data
      return {
        count: groups.length,
        next: null,
        previous: null,
        results: groups,
      }
    } catch (error: unknown) {
      console.error('Get groups by type failed:', error)
      throw error
    }
  }

  // Get groups summary
  async getGroupsSummary(): Promise<GroupsSummary> {
    try {
      const response = await httpClient.get<GroupsSummary>(API_ENDPOINTS.GROUPS.SUMMARY)
      return response.data
    } catch (error: unknown) {
      console.error('Get groups summary failed:', error)
      throw error
    }
  }

  // Get single group
  async getGroup(groupId: string): Promise<GenericGroup> {
    try {
      const response = await httpClient.get<GenericGroup>(API_ENDPOINTS.GROUPS.DETAIL(groupId))
      return response.data
    } catch (error: unknown) {
      console.error('Get group failed:', error)
      throw error
    }
  }

  // Create group
  async createGroup(data: CreateGroupRequest): Promise<GenericGroup> {
    try {
      // Backend expects `initial_members` objects to use the key `key`, not `member_key`.
      const payload: any = { ...data }
      if (Array.isArray(data.initial_members)) {
        payload.initial_members = data.initial_members.map((m) => ({
          key: m.member_key,
          label: m.label,
          tags: m.tags,
          metadata: m.metadata,
        }))
      }
      const response = await httpClient.post<GenericGroup>(API_ENDPOINTS.GROUPS.CREATE, payload)
      return response.data
    } catch (error: unknown) {
      console.error('Create group failed:', error)
      throw error
    }
  }

  // Update group
  async updateGroup(groupId: string, data: UpdateGroupRequest): Promise<GenericGroup> {
    try {
      const response = await httpClient.patch<GenericGroup>(
        API_ENDPOINTS.GROUPS.UPDATE(groupId),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Update group failed:', error)
      throw error
    }
  }

  // Delete group
  async deleteGroup(groupId: string): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.GROUPS.DELETE(groupId))
    } catch (error: unknown) {
      console.error('Delete group failed:', error)
      throw error
    }
  }

  // ============================================
  // MEMBER MANAGEMENT
  // ============================================

  // Add members to group
  async addMembers(groupId: string, data: AddMembersRequest): Promise<AddMembersResponse> {
    try {
      const response = await httpClient.post<AddMembersResponse>(
        API_ENDPOINTS.GROUPS.ADD_MEMBERS(groupId),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Add members failed:', error)
      throw error
    }
  }

  // Update metadata for existing members
  async updateMembers(groupId: string, data: UpdateMembersRequest): Promise<UpdateMembersResponse> {
    try {
      const response = await httpClient.post<UpdateMembersResponse>(
        API_ENDPOINTS.GROUPS.UPDATE_MEMBERS(groupId),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Update members failed:', error)
      throw error
    }
  }

  // Remove members from group
  async removeMembers(groupId: string, data: RemoveMembersRequest): Promise<RemoveMembersResponse> {
    try {
      const response = await httpClient.post<RemoveMembersResponse>(
        API_ENDPOINTS.GROUPS.REMOVE_MEMBERS(groupId),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Remove members failed:', error)
      throw error
    }
  }

  // List members of a group
  async listMembers(groupId: string): Promise<GroupMembersResponse> {
    try {
      const response = await httpClient.get<GroupMembersResponse>(API_ENDPOINTS.GROUPS.LIST_MEMBERS(groupId))
      return response.data
    } catch (error: unknown) {
      console.error('List members failed:', error)
      throw error
    }
  }

  // ============================================
  // SUBSCRIPTIONS
  // ============================================

  // List subscriptions
  async getSubscriptions(
    params: SubscriptionsListParams = {}
  ): Promise<PaginatedResponse<GroupSubscription>> {
    try {
      const response = await httpClient.get<PaginatedResponse<GroupSubscription>>(
        API_ENDPOINTS.SUBSCRIPTIONS.LIST,
        params
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get subscriptions failed:', error)
      throw error
    }
  }

  // Get subscriptions by alert group
  async getSubscriptionsByAlertGroup(
    alertGroupId: string
  ): Promise<PaginatedResponse<GroupSubscription>> {
    try {
      const response = await httpClient.get<PaginatedResponse<GroupSubscription>>(
        API_ENDPOINTS.SUBSCRIPTIONS.BY_ALERT_GROUP,
        { alert_group_id: alertGroupId }
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get subscriptions by alert group failed:', error)
      throw error
    }
  }

  // Get subscriptions by target group
  async getSubscriptionsByTargetGroup(
    targetGroupId: string
  ): Promise<PaginatedResponse<GroupSubscription>> {
    try {
      const response = await httpClient.get<PaginatedResponse<GroupSubscription>>(
        API_ENDPOINTS.SUBSCRIPTIONS.BY_TARGET_GROUP,
        { target_group_id: targetGroupId }
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get subscriptions by target group failed:', error)
      throw error
    }
  }

  // Get single subscription
  async getSubscription(subscriptionId: string): Promise<GroupSubscription> {
    try {
      const response = await httpClient.get<GroupSubscription>(
        API_ENDPOINTS.SUBSCRIPTIONS.DETAIL(subscriptionId)
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get subscription failed:', error)
      throw error
    }
  }

  // Create subscription
  async createSubscription(data: CreateSubscriptionRequest): Promise<GroupSubscription> {
    try {
      const response = await httpClient.post<GroupSubscription>(
        API_ENDPOINTS.SUBSCRIPTIONS.CREATE,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Create subscription failed:', error)
      throw error
    }
  }

  // Update subscription
  async updateSubscription(
    subscriptionId: string,
    data: UpdateSubscriptionRequest
  ): Promise<GroupSubscription> {
    try {
      const response = await httpClient.patch<GroupSubscription>(
        API_ENDPOINTS.SUBSCRIPTIONS.UPDATE(subscriptionId),
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Update subscription failed:', error)
      throw error
    }
  }

  // Delete subscription
  async deleteSubscription(subscriptionId: string): Promise<void> {
    try {
      await httpClient.delete(API_ENDPOINTS.SUBSCRIPTIONS.DELETE(subscriptionId))
    } catch (error: unknown) {
      console.error('Delete subscription failed:', error)
      throw error
    }
  }

  // Toggle subscription active status
  async toggleSubscription(subscriptionId: string): Promise<GroupSubscription> {
    try {
      const response = await httpClient.post<GroupSubscription>(
        API_ENDPOINTS.SUBSCRIPTIONS.TOGGLE(subscriptionId)
      )
      return response.data
    } catch (error: unknown) {
      console.error('Toggle subscription failed:', error)
      throw error
    }
  }

  // ============================================
  // CONVENIENCE METHODS
  // ============================================

  // Get wallet groups
  async getWalletGroups(
    params: Omit<GroupsListParams, 'group_type'> = {}
  ): Promise<PaginatedResponse<GenericGroup>> {
    return this.getGroupsByType(GroupType.WALLET, params)
  }

  // Get alert groups
  async getAlertGroups(
    params: Omit<GroupsListParams, 'group_type'> = {}
  ): Promise<PaginatedResponse<GenericGroup>> {
    return this.getGroupsByType(GroupType.ALERT, params)
  }

  // Get network groups
  async getNetworkGroups(
    params: Omit<GroupsListParams, 'group_type'> = {}
  ): Promise<PaginatedResponse<GenericGroup>> {
    return this.getGroupsByType(GroupType.NETWORK, params)
  }

  // Get token groups
  async getTokenGroups(
    params: Omit<GroupsListParams, 'group_type'> = {}
  ): Promise<PaginatedResponse<GenericGroup>> {
    return this.getGroupsByType(GroupType.TOKEN, params)
  }

  // Create a wallet group
  async createWalletGroup(
    name: string,
    description?: string,
    walletAddresses?: string[]
  ): Promise<GenericGroup> {
    const initialMembers = walletAddresses?.map((address) => ({
      member_key: address,
      label: address.slice(0, 8) + '...' + address.slice(-6),
    }))

    return this.createGroup({
      group_type: GroupType.WALLET,
      name,
      description,
      initial_members: initialMembers,
    })
  }

  // Create an alert group
  // alertType specifies what type of targets this alert group monitors (wallet, network, or token)
  async createAlertGroup(
    name: string,
    description?: string,
    alertType: 'wallet' | 'network' | 'protocol' | 'token' | 'contract' | 'nft' = 'wallet'
  ): Promise<GenericGroup> {
    return this.createGroup({
      group_type: GroupType.ALERT,
      name,
      description,
      settings: {
        alert_type: alertType,
      },
    })
  }

  // Subscribe an alert group to a wallet group
  async subscribeAlertToWallets(
    alertGroupId: string,
    walletGroupId: string
  ): Promise<GroupSubscription> {
    return this.createSubscription({
      alert_group: alertGroupId,
      target_group: walletGroupId,
    })
  }

  // ============================================
  // ACCOUNTS (System Group)
  // ============================================

  async getAccountsGroup(): Promise<GenericGroup | null> {
    try {
      const response = await httpClient.get<GenericGroup>(API_ENDPOINTS.GROUPS.ACCOUNTS)
      return response.data
    } catch (error: any) {
      // 404 means the user hasn't created Accounts yet (lazy creation)
      if (error?.status === 404) {
        return null
      }
      console.error('Get accounts group failed:', error)
      throw error
    }
  }

  async addWalletToAccounts(data: AccountsAddWalletRequest): Promise<AccountsAddWalletResponse> {
    try {
      const response = await httpClient.post<AccountsAddWalletResponse>(
        API_ENDPOINTS.GROUPS.ACCOUNTS_ADD_WALLET,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Add wallet to accounts failed:', error)
      throw error
    }
  }

  async addWalletsToAccounts(data: AccountsAddWalletsRequest): Promise<AccountsAddWalletsResponse> {
    try {
      const response = await httpClient.post<AccountsAddWalletsResponse>(
        API_ENDPOINTS.GROUPS.ACCOUNTS_ADD_WALLETS,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Bulk add wallets to accounts failed:', error)
      throw error
    }
  }

  // ============================================
  // ALERTGROUP TEMPLATE DISCOVERY
  // ============================================

  async getAlertGroupTemplates(alertGroupId: string): Promise<AlertGroupTemplatesResponse> {
    try {
      const response = await httpClient.get<AlertGroupTemplatesResponse>(
        API_ENDPOINTS.GROUPS.TEMPLATES(alertGroupId)
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get alert group templates failed:', error)
      throw error
    }
  }

  // ============================================
  // USER WALLET GROUPS (Provider-Managed)
  // ============================================

  // Get user wallet groups (provider-managed associations)
  async getUserWalletGroups(): Promise<PaginatedResponse<UserWalletGroup>> {
    try {
      const response = await httpClient.get<PaginatedResponse<UserWalletGroup>>(
        '/api/groups/user-wallet-groups/'
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get user wallet groups failed:', error)
      throw error
    }
  }

  // Get a single user wallet group
  async getUserWalletGroup(id: string): Promise<UserWalletGroup> {
    try {
      const response = await httpClient.get<UserWalletGroup>(
        `/api/groups/user-wallet-groups/${id}/`
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get user wallet group failed:', error)
      throw error
    }
  }

  // Update user wallet group (notification routing, auto-subscribe)
  async updateUserWalletGroup(
    id: string,
    data: UpdateUserWalletGroupRequest
  ): Promise<UserWalletGroup> {
    try {
      const response = await httpClient.patch<UserWalletGroup>(
        `/api/groups/user-wallet-groups/${id}/`,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Update user wallet group failed:', error)
      throw error
    }
  }

  async deleteUserWalletGroup(id: string): Promise<void> {
    try {
      await httpClient.delete(`/api/groups/user-wallet-groups/${id}/`)
    } catch (error: unknown) {
      console.error('Delete user wallet group failed:', error)
      throw error
    }
  }

  async createUserWalletGroup(
    data: CreateUserWalletGroupRequest
  ): Promise<UserWalletGroup> {
    try {
      const response = await httpClient.post<UserWalletGroup>(
        '/api/groups/user-wallet-groups/',
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Create user wallet group failed:', error)
      throw error
    }
  }

  async addUserWalletGroupWallets(
    id: string,
    data: { wallet_keys: string[]; dedupe?: boolean }
  ): Promise<UserWalletGroupWalletsResponse> {
    try {
      const response = await httpClient.post<UserWalletGroupWalletsResponse>(
        `/api/groups/user-wallet-groups/${id}/add_wallets/`,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Add user wallet group wallets failed:', error)
      throw error
    }
  }

  async removeUserWalletGroupWallets(
    id: string,
    data: { wallet_keys: string[] }
  ): Promise<UserWalletGroupWalletsResponse> {
    try {
      const response = await httpClient.post<UserWalletGroupWalletsResponse>(
        `/api/groups/user-wallet-groups/${id}/remove_wallets/`,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Remove user wallet group wallets failed:', error)
      throw error
    }
  }

  async importUserWalletGroupWallets(
    id: string,
    data: {
      format: 'csv' | 'json'
      payload: string
      merge_mode?: 'append' | 'replace'
      dedupe?: boolean
    }
  ): Promise<UserWalletGroupImportResponse> {
    try {
      const response = await httpClient.post<UserWalletGroupImportResponse>(
        `/api/groups/user-wallet-groups/${id}/import_wallets/`,
        data
      )
      return response.data
    } catch (error: unknown) {
      console.error('Import user wallet group wallets failed:', error)
      throw error
    }
  }

  // ============================================
  // DEFAULT NETWORK ALERTS
  // ============================================

  // Get default network alerts (fallback alerts per chain/subnet)
  async getDefaultNetworkAlerts(): Promise<PaginatedResponse<DefaultNetworkAlert>> {
    try {
      const response = await httpClient.get<PaginatedResponse<DefaultNetworkAlert>>(
        '/api/alerts/default-network/'
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get default network alerts failed:', error)
      throw error
    }
  }

  // Get a single default network alert
  async getDefaultNetworkAlert(id: string): Promise<DefaultNetworkAlert> {
    try {
      const response = await httpClient.get<DefaultNetworkAlert>(
        `/api/alerts/default-network/${id}/`
      )
      return response.data
    } catch (error: unknown) {
      console.error('Get default network alert failed:', error)
      throw error
    }
  }

  // Toggle default network alert enabled status
  async toggleDefaultNetworkAlert(id: string, enabled: boolean): Promise<DefaultNetworkAlert> {
    try {
      const response = await httpClient.patch<DefaultNetworkAlert>(
        `/api/alerts/default-network/${id}/`,
        { enabled }
      )
      return response.data
    } catch (error: unknown) {
      console.error('Toggle default network alert failed:', error)
      throw error
    }
  }
}

export const groupsApiService = new GroupsApiService()
export default groupsApiService
