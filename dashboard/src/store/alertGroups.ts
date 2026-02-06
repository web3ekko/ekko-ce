/**
 * Alert Groups Store
 *
 * State management for alert groups using the unified Groups API
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import groupsApiService, {
  type GenericGroup,
  type GroupSubscription,
  GroupType,
} from '../services/groups-api'

// Re-export types for backwards compatibility
export type { GenericGroup as AlertGroup } from '../services/groups-api'

interface AlertGroupsState {
  // State
  myGroups: GenericGroup[]
  publicGroups: GenericGroup[]
  groups: GenericGroup[]
  subscriptions: GroupSubscription[]
  isLoading: boolean
  error: string | null
  searchQuery: string
  filterCategory: string | null

  // Actions
  loadGroups: () => Promise<void>
  loadSubscriptions: () => Promise<void>
  createGroup: (name: string, description?: string) => Promise<GenericGroup>
  updateGroup: (groupId: string, data: { name?: string; description?: string }) => Promise<void>
  deleteGroup: (groupId: string) => Promise<void>
  addMembers: (
    groupId: string,
    members: Array<{ member_key: string; label?: string }>
  ) => Promise<void>
  removeMembers: (groupId: string, memberKeys: string[]) => Promise<void>
  createSubscription: (params: {
    alertGroupId: string
    targetGroupId?: string | null
    targetKey?: string | null
    templateParams?: Record<string, unknown>
  }) => Promise<GroupSubscription>
  deleteSubscription: (subscriptionId: string) => Promise<void>
  toggleSubscription: (subscriptionId: string) => Promise<void>
  setSearchQuery: (query: string) => void
  setFilterCategory: (category: string | null) => void
  setError: (error: string | null) => void
}

export const useAlertGroupsStore = create<AlertGroupsState>()(
  persist(
    (set, get) => ({
      // Initial state
      myGroups: [],
      publicGroups: [],
      groups: [],
      subscriptions: [],
      isLoading: false,
      error: null,
      searchQuery: '',
      filterCategory: null,

      // Load all alert groups
      loadGroups: async () => {
        set({ isLoading: true, error: null })

        try {
          const response = await groupsApiService.getGroupsSplit({ group_type: GroupType.ALERT })
          const myGroups = response.my_groups.results
          const publicGroups = response.public_groups.results
          set({
            myGroups,
            publicGroups,
            groups: [...myGroups, ...publicGroups],
            isLoading: false,
          })
        } catch {
          set({
            error: 'Failed to load alert groups',
            isLoading: false,
          })
        }
      },

      // Load user's subscriptions
      loadSubscriptions: async () => {
        try {
          const response = await groupsApiService.getSubscriptions()
          set({ subscriptions: response.results })
        } catch {
          set({ error: 'Failed to load subscriptions' })
        }
      },

      // Create a new alert group
      createGroup: async (name: string, description?: string) => {
        try {
          const newGroup = await groupsApiService.createAlertGroup(name, description)
          set((state) => ({
            myGroups: [...state.myGroups, newGroup],
            groups: [...state.groups, newGroup],
          }))
          return newGroup
        } catch {
          set({ error: 'Failed to create alert group' })
          throw new Error('Failed to create alert group')
        }
      },

      // Update an alert group
      updateGroup: async (groupId: string, data: { name?: string; description?: string }) => {
        try {
          const updatedGroup = await groupsApiService.updateGroup(groupId, data)
          set((state) => ({
            myGroups: state.myGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            publicGroups: state.publicGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            groups: state.groups.map((g) => (g.id === groupId ? updatedGroup : g)),
          }))
        } catch {
          set({ error: 'Failed to update alert group' })
        }
      },

      // Delete an alert group
      deleteGroup: async (groupId: string) => {
        try {
          await groupsApiService.deleteGroup(groupId)
          set((state) => ({
            myGroups: state.myGroups.filter((g) => g.id !== groupId),
            publicGroups: state.publicGroups.filter((g) => g.id !== groupId),
            groups: state.groups.filter((g) => g.id !== groupId),
            // Also remove any subscriptions involving this group
            subscriptions: state.subscriptions.filter(
              (s) => s.alert_group !== groupId && s.target_group !== groupId
            ),
          }))
        } catch {
          set({ error: 'Failed to delete alert group' })
        }
      },

      // Add members to an alert group
      addMembers: async (
        groupId: string,
        members: Array<{ member_key: string; label?: string }>
      ) => {
        try {
          await groupsApiService.addMembers(groupId, { members })
          const updatedGroup = await groupsApiService.getGroup(groupId)
          set((state) => ({
            myGroups: state.myGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            publicGroups: state.publicGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            groups: state.groups.map((g) => (g.id === groupId ? updatedGroup : g)),
          }))
        } catch {
          set({ error: 'Failed to add members to group' })
        }
      },

      // Remove members from an alert group
      removeMembers: async (groupId: string, memberKeys: string[]) => {
        try {
          await groupsApiService.removeMembers(groupId, {
            members: memberKeys.map((memberKey) => ({ member_key: memberKey })),
          })
          const updatedGroup = await groupsApiService.getGroup(groupId)
          set((state) => ({
            myGroups: state.myGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            publicGroups: state.publicGroups.map((g) => (g.id === groupId ? updatedGroup : g)),
            groups: state.groups.map((g) => (g.id === groupId ? updatedGroup : g)),
          }))
        } catch {
          set({ error: 'Failed to remove members from group' })
        }
      },

      // Create a subscription (link alert group to target group)
      createSubscription: async ({ alertGroupId, targetGroupId = null, targetKey = null, templateParams }) => {
        try {
          const newSubscription = await groupsApiService.createSubscription({
            alert_group: alertGroupId,
            target_group: targetGroupId || null,
            target_key: targetGroupId ? null : (targetKey || null),
            settings: templateParams ? { template_params: templateParams } : undefined,
          })
          set((state) => ({
            subscriptions: [...state.subscriptions, newSubscription],
          }))
          return newSubscription
        } catch {
          set({ error: 'Failed to create subscription' })
          throw new Error('Failed to create subscription')
        }
      },

      // Delete a subscription
      deleteSubscription: async (subscriptionId: string) => {
        try {
          await groupsApiService.deleteSubscription(subscriptionId)
          set((state) => ({
            subscriptions: state.subscriptions.filter((s) => s.id !== subscriptionId),
          }))
        } catch {
          set({ error: 'Failed to delete subscription' })
        }
      },

      // Toggle a subscription's active status
      toggleSubscription: async (subscriptionId: string) => {
        try {
          const updatedSubscription = await groupsApiService.toggleSubscription(subscriptionId)
          set((state) => ({
            subscriptions: state.subscriptions.map((s) =>
              s.id === subscriptionId ? updatedSubscription : s
            ),
          }))
        } catch {
          set({ error: 'Failed to toggle subscription' })
        }
      },

      // Set search query
      setSearchQuery: (query) => {
        set({ searchQuery: query })
      },

      // Set category filter
      setFilterCategory: (category) => {
        set({ filterCategory: category })
      },

      // Set error
      setError: (error) => {
        set({ error })
      },
    }),
    {
      name: 'ekko-alert-groups-storage',
      partialize: (state) => ({
        subscriptions: state.subscriptions,
      }),
    }
  )
)

// Selector helpers
export const selectAlertGroups = (state: AlertGroupsState) => state.groups

export const selectSubscriptions = (state: AlertGroupsState) => state.subscriptions

export const selectSubscribedGroupIds = (state: AlertGroupsState) =>
  new Set(state.subscriptions.map((s) => s.alert_group))

export const selectIsSubscribed = (groupId: string) => (state: AlertGroupsState) =>
  state.subscriptions.some((s) => s.alert_group === groupId)

// Helper to get subscribed groups (groups that have active subscriptions)
export const selectSubscribedGroups = (state: AlertGroupsState) => {
  const subscribedIds = new Set(state.subscriptions.map((s) => s.alert_group))
  return state.groups.filter((g) => subscribedIds.has(g.id))
}

// Helper to extract settings-based properties from GenericGroup
export const getGroupCategory = (group: GenericGroup): string => {
  const settings = group.settings as { category?: string } | undefined
  return settings?.category || 'Uncategorized'
}

export const getGroupTags = (group: GenericGroup): string[] => {
  const settings = group.settings as { tags?: string[] } | undefined
  return settings?.tags || []
}

export const getGroupIsPublic = (group: GenericGroup): boolean => {
  const settings = group.settings as { visibility?: string } | undefined
  return settings?.visibility === 'public'
}
