/**
 * Wallet/Accounts Store
 *
 * Source of truth for "Accounts" (system wallet group) + user-created wallet groups.
 *
 * Accounts are represented as a `GenericGroup` with:
 * - group_type="wallet"
 * - settings.system_key="accounts"
 * - settings.visibility="private"
 *
 * Wallet keys are canonical: {NETWORK}:{subnet}:{address}
 */

import { create } from 'zustand'
import groupsApiService, {
  type AccountsAddWalletRequest,
  type GenericGroup,
  GroupType,
} from '../services/groups-api'

export interface AccountWallet {
  wallet_key: string
  network: string
  subnet: string
  address: string
  label?: string
  owner_verified?: boolean
  added_at?: string
}

export interface WalletStoreState {
  accountsGroup: GenericGroup | null
  accounts: AccountWallet[]
  walletGroups: GenericGroup[]

  isLoading: boolean
  error: string | null

  loadAccounts: () => Promise<void>
  loadWalletGroups: () => Promise<void>
  addAccountWallet: (data: AccountsAddWalletRequest) => Promise<void>
  removeAccountWallet: (walletKey: string) => Promise<void>
  updateAccountWallet: (walletKey: string, updates: { label?: string; owner_verified?: boolean }) => Promise<void>
  createWalletGroup: (data: { name: string; description?: string; settings?: Record<string, unknown> }) => Promise<GenericGroup>
  updateWalletGroup: (groupId: string, data: { name?: string; description?: string; settings?: Record<string, unknown> }) => Promise<void>
  deleteWalletGroup: (groupId: string) => Promise<void>
}

function parseWalletKey(walletKey: string): { network: string; subnet: string; address: string } {
  const parts = walletKey.split(':')
  const network = (parts[0] || '').trim()
  const subnet = (parts[1] || '').trim()
  const address = parts.slice(2).join(':').trim()
  return { network, subnet, address }
}

function groupToAccounts(group: GenericGroup | null): AccountWallet[] {
  if (!group) return []
  const members = group.member_data?.members || {}

  return Object.entries(members).map(([wallet_key, meta]) => {
    const { network, subnet, address } = parseWalletKey(wallet_key)
    const metadata = (meta?.metadata || {}) as { owner_verified?: boolean }

    return {
      wallet_key,
      network,
      subnet,
      address,
      label: meta?.label || undefined,
      owner_verified: metadata.owner_verified || false,
      added_at: meta?.added_at,
    }
  })
}

export const useWalletStore = create<WalletStoreState>((set, get) => ({
  accountsGroup: null,
  accounts: [],
  walletGroups: [],
  isLoading: false,
  error: null,

  loadAccounts: async () => {
    set({ isLoading: true, error: null })
    try {
      const accountsGroup = await groupsApiService.getAccountsGroup()
      set({
        accountsGroup,
        accounts: groupToAccounts(accountsGroup),
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to load accounts:', error)
      set({ error: 'Failed to load accounts', isLoading: false })
    }
  },

  loadWalletGroups: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await groupsApiService.getGroupsByType(GroupType.WALLET)
      set({ walletGroups: response.results, isLoading: false })
    } catch (error) {
      console.error('Failed to load wallet groups:', error)
      set({ error: 'Failed to load wallet groups', isLoading: false })
    }
  },

  addAccountWallet: async (data) => {
    set({ isLoading: true, error: null })
    try {
      await groupsApiService.addWalletToAccounts(data)
      // Reload to refresh member_data + derived accounts list
      const accountsGroup = await groupsApiService.getAccountsGroup()
      set({
        accountsGroup,
        accounts: groupToAccounts(accountsGroup),
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to add account wallet:', error)
      set({ error: 'Failed to add wallet to accounts', isLoading: false })
      throw error
    }
  },

  removeAccountWallet: async (walletKey) => {
    const accountsGroup = get().accountsGroup || (await groupsApiService.getAccountsGroup())
    if (!accountsGroup) {
      set({ error: 'Accounts group not found' })
      return
    }

    set({ isLoading: true, error: null })
    try {
      await groupsApiService.removeMembers(accountsGroup.id, {
        members: [{ member_key: walletKey }],
      })

      const refreshed = await groupsApiService.getAccountsGroup()
      set({
        accountsGroup: refreshed,
        accounts: groupToAccounts(refreshed),
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to remove account wallet:', error)
      set({ error: 'Failed to remove wallet from accounts', isLoading: false })
      throw error
    }
  },

  updateAccountWallet: async (walletKey, updates) => {
    const accountsGroup = get().accountsGroup || (await groupsApiService.getAccountsGroup())
    if (!accountsGroup) {
      set({ error: 'Accounts group not found' })
      return
    }

    const memberUpdate: {
      member_key: string
      label?: string
      metadata?: Record<string, unknown>
    } = { member_key: walletKey }

    if (updates.label !== undefined) {
      memberUpdate.label = updates.label
    }

    if (typeof updates.owner_verified === 'boolean') {
      memberUpdate.metadata = { owner_verified: updates.owner_verified }
    }

    set({ isLoading: true, error: null })
    try {
      await groupsApiService.updateMembers(accountsGroup.id, { members: [memberUpdate] })
      const refreshed = await groupsApiService.getAccountsGroup()
      set({
        accountsGroup: refreshed,
        accounts: groupToAccounts(refreshed),
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to update account wallet:', error)
      set({ error: 'Failed to update account wallet', isLoading: false })
      throw error
    }
  },

  createWalletGroup: async ({ name, description, settings }) => {
    set({ isLoading: true, error: null })
    try {
      const group = await groupsApiService.createGroup({
        group_type: GroupType.WALLET,
        name,
        description,
        settings,
      })

      // Refresh list (list endpoints are authoritative for ordering/filtering)
      const refreshed = await groupsApiService.getGroupsByType(GroupType.WALLET)
      set({ walletGroups: refreshed.results, isLoading: false })
      return group
    } catch (error) {
      console.error('Failed to create wallet group:', error)
      set({ error: 'Failed to create wallet group', isLoading: false })
      throw error
    }
  },

  updateWalletGroup: async (groupId, data) => {
    set({ isLoading: true, error: null })
    try {
      await groupsApiService.updateGroup(groupId, data)
      const refreshed = await groupsApiService.getGroupsByType(GroupType.WALLET)
      set({ walletGroups: refreshed.results, isLoading: false })
    } catch (error) {
      console.error('Failed to update wallet group:', error)
      set({ error: 'Failed to update wallet group', isLoading: false })
      throw error
    }
  },

  deleteWalletGroup: async (groupId) => {
    set({ isLoading: true, error: null })
    try {
      await groupsApiService.deleteGroup(groupId)
      const refreshed = await groupsApiService.getGroupsByType(GroupType.WALLET)
      set({ walletGroups: refreshed.results, isLoading: false })
    } catch (error) {
      console.error('Failed to delete wallet group:', error)
      set({ error: 'Failed to delete wallet group', isLoading: false })
      throw error
    }
  },
}))
