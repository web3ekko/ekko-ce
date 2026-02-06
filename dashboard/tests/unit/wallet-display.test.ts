import { describe, expect, it } from 'vitest'

import { parseWalletKey, truncateMiddle } from '../../src/utils/wallet-display'

describe('wallet-display utils', () => {
  it('parseWalletKey splits network/subnet/address', () => {
    expect(parseWalletKey('ETH:mainnet:0xabc')).toEqual({
      network: 'ETH',
      subnet: 'mainnet',
      address: '0xabc',
    })
  })

  it('truncateMiddle truncates long strings', () => {
    expect(truncateMiddle('0x1234567890abcdef', 6, 4)).toBe('0x1234...cdef')
  })
})

