export function truncateMiddle(value: string, prefix: number = 6, suffix: number = 4): string {
  if (value.length <= prefix + suffix + 3) return value
  return `${value.slice(0, prefix)}...${value.slice(-suffix)}`
}

export function parseWalletKey(walletKey: string): { network: string; subnet: string; address: string } {
  const parts = walletKey.split(':')
  const network = (parts[0] || '').trim()
  const subnet = (parts[1] || '').trim()
  const address = parts.slice(2).join(':').trim()
  return { network, subnet, address }
}

