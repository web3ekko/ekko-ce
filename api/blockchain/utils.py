"""
Blockchain utilities and validation functions
"""

from typing import Tuple, Dict, List, Optional


def validate_network(chain: str, subnet: str) -> Tuple[bool, Optional[str]]:
    """
    Validate blockchain network and subnet combination
    
    Args:
        chain: Blockchain identifier (e.g., 'ETH', 'BTC', 'SOL')
        subnet: Network subnet (e.g., 'mainnet', 'testnet', 'goerli')
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    # Define valid network combinations
    VALID_NETWORKS = {
        'ETH': ['mainnet', 'goerli', 'sepolia', 'holesky'],
        'BTC': ['mainnet', 'testnet', 'regtest'],
        'SOL': ['mainnet-beta', 'testnet', 'devnet'],
        'MATIC': ['mainnet', 'mumbai'],
        'AVAX': ['mainnet', 'fuji'],
        'BNB': ['mainnet', 'testnet'],
        'ARB': ['mainnet', 'goerli'],
        'OP': ['mainnet', 'goerli'],
    }
    
    chain_upper = chain.upper()
    subnet_lower = subnet.lower()
    
    if chain_upper not in VALID_NETWORKS:
        return False, f"Unknown blockchain: {chain}"
    
    if subnet_lower not in VALID_NETWORKS[chain_upper]:
        return False, f"Invalid subnet '{subnet}' for {chain_upper}. Valid options: {', '.join(VALID_NETWORKS[chain_upper])}"
    
    return True, None


def validate_address(address: str, chain: str) -> Tuple[bool, Optional[str]]:
    """
    Validate blockchain address format
    
    Args:
        address: The wallet address to validate
        chain: Blockchain identifier
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    chain_upper = chain.upper()
    
    if chain_upper == 'ETH':
        # Ethereum address validation
        if not address.startswith('0x'):
            return False, "Ethereum address must start with '0x'"
        if len(address) != 42:
            return False, "Ethereum address must be 42 characters long"
        try:
            int(address[2:], 16)
        except ValueError:
            return False, "Ethereum address contains invalid hexadecimal characters"
        return True, None
    
    elif chain_upper == 'BTC':
        # Bitcoin address validation
        # P2PKH addresses (Legacy)
        if address.startswith('1') and 26 <= len(address) <= 35:
            return True, None
        # P2SH addresses
        if address.startswith('3') and 26 <= len(address) <= 35:
            return True, None
        # Bech32 addresses (SegWit)
        if address.startswith('bc1') and len(address) >= 42:
            return True, None
        # Testnet addresses
        if address.startswith(('tb1', 'n', 'm', '2')):
            return True, None
        return False, "Invalid Bitcoin address format"
    
    elif chain_upper == 'SOL':
        # Solana address validation
        if 32 <= len(address) <= 44:
            return True, None
        return False, "Solana address must be between 32 and 44 characters"
    
    else:
        # Basic validation for unknown chains
        if len(address) < 10:
            return False, f"Address too short for {chain}"
        return True, None


def normalize_address(address: str, chain: str) -> str:
    """
    Normalize blockchain address for consistent storage
    
    Args:
        address: The wallet address to normalize
        chain: Blockchain identifier
    
    Returns:
        Normalized address
    """
    chain_upper = chain.upper()
    
    if chain_upper == 'ETH':
        # Ethereum addresses are case-insensitive
        return address.lower()
    elif chain_upper == 'BTC':
        # Bitcoin addresses are case-sensitive
        return address
    elif chain_upper == 'SOL':
        # Solana addresses are case-sensitive
        return address
    else:
        # Default: preserve original case
        return address


def format_wallet_key(chain: str, subnet: str, address: str) -> str:
    """
    Format a wallet key for consistent storage
    
    Args:
        chain: Blockchain identifier
        subnet: Network subnet
        address: Wallet address
    
    Returns:
        Formatted wallet key (e.g., 'ETH:mainnet:0x123...')
    """
    normalized_address = normalize_address(address, chain)
    return f"{chain.upper()}:{subnet.lower()}:{normalized_address}"


def parse_wallet_key(wallet_key: str) -> Dict[str, str]:
    """
    Parse a wallet key into its components
    
    Args:
        wallet_key: Formatted wallet key
    
    Returns:
        Dictionary with chain, subnet, and address
    """
    parts = wallet_key.split(':')
    if len(parts) != 3:
        raise ValueError(f"Invalid wallet key format: {wallet_key}")
    
    return {
        'chain': parts[0],
        'subnet': parts[1],
        'address': parts[2]
    }


def get_chain_display_name(chain: str) -> str:
    """
    Get display name for a blockchain
    
    Args:
        chain: Blockchain identifier
    
    Returns:
        Human-friendly display name
    """
    DISPLAY_NAMES = {
        'ETH': 'Ethereum',
        'BTC': 'Bitcoin',
        'SOL': 'Solana',
        'MATIC': 'Polygon',
        'AVAX': 'Avalanche',
        'BNB': 'Binance Smart Chain',
        'ARB': 'Arbitrum',
        'OP': 'Optimism',
    }
    
    return DISPLAY_NAMES.get(chain.upper(), chain.upper())


def get_subnet_display_name(subnet: str) -> str:
    """
    Get display name for a network subnet
    
    Args:
        subnet: Network subnet identifier
    
    Returns:
        Human-friendly display name
    """
    DISPLAY_NAMES = {
        'mainnet': 'Mainnet',
        'testnet': 'Testnet',
        'goerli': 'Goerli Testnet',
        'sepolia': 'Sepolia Testnet',
        'holesky': 'Holesky Testnet',
        'mumbai': 'Mumbai Testnet',
        'fuji': 'Fuji Testnet',
        'mainnet-beta': 'Mainnet Beta',
        'devnet': 'Devnet',
        'regtest': 'Regtest',
    }
    
    return DISPLAY_NAMES.get(subnet.lower(), subnet.title())