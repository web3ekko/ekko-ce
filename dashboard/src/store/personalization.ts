/**
 * Personalization store
 *
 * Client-side cache of user personalization data:
 * - Wallet nicknames (fallback names for wallet addresses)
 * - Chain metadata (network -> chain_id mapping)
 */

import { create } from 'zustand'
import chainsApiService, { type ChainInfo } from '../services/chains-api'
import walletNicknamesApiService, { type WalletNickname } from '../services/wallet-nicknames-api'

type WalletNicknamesByKey = Record<string, WalletNickname>

export interface PersonalizationState {
  walletNicknames: WalletNickname[]
  walletNicknameByKey: WalletNicknamesByKey
  walletNicknameByAddress: Record<string, string>

  chains: ChainInfo[]
  chainIdByNetwork: Record<string, number>

  isLoadingNicknames: boolean
  isLoadingChains: boolean
  error: string | null

  loadWalletNicknames: () => Promise<void>
  loadChains: () => Promise<void>

  getChainId: (network: string) => number | null
  getWalletNickname: (address: string, chainId: number | null) => string | null
  getWalletNicknameRecord: (address: string, chainId: number | null) => WalletNickname | null
}

function normalizeAddressForLookup(address: string): string {
  return address.trim().toLowerCase()
}

function normalizeNetwork(network: string): string {
  return network.trim().toUpperCase()
}

function buildAddressChainKey(address: string, chainId: number): string {
  return `${normalizeAddressForLookup(address)}:${chainId}`
}

function buildChainIdByNetwork(chains: ChainInfo[]): Record<string, number> {
  const out: Record<string, number> = {}
  for (const chain of chains) {
    if (typeof chain.chain_id !== 'number') continue

    if (chain.native_token) {
      out[normalizeNetwork(chain.native_token)] = chain.chain_id
    }
    if (chain.name) {
      out[normalizeNetwork(chain.name)] = chain.chain_id
    }
    if (chain.display_name) {
      out[normalizeNetwork(chain.display_name)] = chain.chain_id
    }
  }
  return out
}

function buildNicknameMaps(nicknames: WalletNickname[]): {
  walletNicknameByKey: WalletNicknamesByKey
  walletNicknameByAddress: Record<string, string>
} {
  const byKey: WalletNicknamesByKey = {}
  const candidates: Record<string, Set<string>> = {}

  for (const row of nicknames) {
    const key = buildAddressChainKey(row.wallet_address, row.chain_id)
    byKey[key] = row

    const addressKey = normalizeAddressForLookup(row.wallet_address)
    if (!candidates[addressKey]) candidates[addressKey] = new Set()
    candidates[addressKey].add(row.custom_name)
  }

  const byAddress: Record<string, string> = {}
  for (const [addressKey, names] of Object.entries(candidates)) {
    if (names.size === 1) {
      byAddress[addressKey] = [...names][0]
    }
  }

  return { walletNicknameByKey: byKey, walletNicknameByAddress: byAddress }
}

export const usePersonalizationStore = create<PersonalizationState>((set, get) => ({
  walletNicknames: [],
  walletNicknameByKey: {},
  walletNicknameByAddress: {},

  chains: [],
  chainIdByNetwork: {},

  isLoadingNicknames: false,
  isLoadingChains: false,
  error: null,

  loadWalletNicknames: async () => {
    set({ isLoadingNicknames: true, error: null })
    try {
      const response = await walletNicknamesApiService.list()
      const nicknames = response.results || []
      const maps = buildNicknameMaps(nicknames)
      set({
        walletNicknames: nicknames,
        walletNicknameByKey: maps.walletNicknameByKey,
        walletNicknameByAddress: maps.walletNicknameByAddress,
        isLoadingNicknames: false,
      })
    } catch (error) {
      console.error('Failed to load wallet nicknames:', error)
      set({ error: 'Failed to load wallet nicknames', isLoadingNicknames: false })
    }
  },

  loadChains: async () => {
    set({ isLoadingChains: true, error: null })
    try {
      const response = await chainsApiService.list()
      const chains = response.results || []
      set({
        chains,
        chainIdByNetwork: buildChainIdByNetwork(chains),
        isLoadingChains: false,
      })
    } catch (error) {
      console.error('Failed to load chains:', error)
      set({ error: 'Failed to load chains', isLoadingChains: false })
    }
  },

  getChainId: (network) => {
    const normalized = normalizeNetwork(network)
    return get().chainIdByNetwork[normalized] ?? null
  },

  getWalletNickname: (address, chainId) => {
    const addressKey = normalizeAddressForLookup(address)

    if (typeof chainId === 'number') {
      const record = get().walletNicknameByKey[buildAddressChainKey(addressKey, chainId)]
      return record?.custom_name ?? null
    }

    return get().walletNicknameByAddress[addressKey] ?? null
  },

  getWalletNicknameRecord: (address, chainId) => {
    if (typeof chainId !== 'number') return null
    const addressKey = normalizeAddressForLookup(address)
    return get().walletNicknameByKey[buildAddressChainKey(addressKey, chainId)] ?? null
  },
}))

