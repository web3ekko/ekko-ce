import { describe, expect, it } from 'vitest'

import { buildNetworkKey, buildTargetKey, getChainIdentity, normalizeChainKey } from '../../src/utils/chain-identity'

describe('chain-identity utils', () => {
  it('normalizes chain aliases and ids', () => {
    expect(normalizeChainKey('ethereum')).toBe('ethereum')
    expect(normalizeChainKey('ETH')).toBe('ethereum')
    expect(normalizeChainKey('ethereum_mainnet')).toBe('ethereum')
    expect(normalizeChainKey(1)).toBe('ethereum')
    expect(normalizeChainKey('avalanche')).toBe('avalanche')
    expect(normalizeChainKey('avax')).toBe('avalanche')
    expect(normalizeChainKey('bsc')).toBe('bsc')
  })

  it('builds network and target keys with canonical casing', () => {
    expect(buildNetworkKey('ethereum')).toBe('ETH:mainnet')
    expect(buildTargetKey('ethereum', '0xABCDEF')).toBe('ETH:mainnet:0xABCDEF')
  })

  it('returns chain identity metadata', () => {
    const identity = getChainIdentity('solana')
    expect(identity?.symbol).toBe('SOL')
    expect(identity?.logo).toBe('/logos/chains/solana.svg')
  })

  it('maps chains to official logo assets', () => {
    expect(getChainIdentity('ethereum')?.logo).toBe('/logos/chains/ethereum.png')
    expect(getChainIdentity('bitcoin')?.logo).toBe('/logos/chains/bitcoin.png')
    expect(getChainIdentity('avalanche')?.logo).toBe('/logos/chains/avalanche.svg')
    expect(getChainIdentity('bsc')?.logo).toBe('/logos/chains/bsc.png')
  })
})
