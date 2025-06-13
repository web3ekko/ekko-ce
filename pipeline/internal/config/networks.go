package config

import (
	"fmt"
	"strings"
)

// NetworkConfig defines configuration for a blockchain network
type NetworkConfig struct {
	Name        string            `yaml:"name" json:"name"`
	ChainID     string            `yaml:"chain_id" json:"chain_id"`
	Subnets     []SubnetConfig    `yaml:"subnets" json:"subnets"`
	DefaultRPC  string            `yaml:"default_rpc" json:"default_rpc"`
	DefaultWS   string            `yaml:"default_ws" json:"default_ws"`
	Explorer    string            `yaml:"explorer" json:"explorer"`
	Currency    string            `yaml:"currency" json:"currency"`
	Enabled     bool              `yaml:"enabled" json:"enabled"`
	Metadata    map[string]string `yaml:"metadata" json:"metadata"`
}

// SubnetConfig defines configuration for a subnet within a network
type SubnetConfig struct {
	Name         string   `yaml:"name" json:"name"`
	ChainID      string   `yaml:"chain_id" json:"chain_id"`
	VMType       string   `yaml:"vm_type" json:"vm_type"`
	NodeURLs     []string `yaml:"node_urls" json:"node_urls"`
	WebSocketURL string   `yaml:"websocket_url" json:"websocket_url"`
	HTTPURL      string   `yaml:"http_url" json:"http_url"`
	StreamName   string   `yaml:"stream_name" json:"stream_name"`
	Subject      string   `yaml:"subject" json:"subject"`
	Enabled      bool     `yaml:"enabled" json:"enabled"`
	Network      string   `yaml:"network" json:"network"` // Parent network name
}

// NetworkRegistry manages all supported networks and their configurations
type NetworkRegistry struct {
	Networks map[string]NetworkConfig `yaml:"networks" json:"networks"`
}

// GetDefaultNetworkRegistry returns the default network configurations
func GetDefaultNetworkRegistry() *NetworkRegistry {
	return &NetworkRegistry{
		Networks: map[string]NetworkConfig{
			"Avalanche": {
				Name:       "Avalanche",
				ChainID:    "43114",
				DefaultRPC: "https://api.avax.network/ext/bc/C/rpc",
				DefaultWS:  "wss://api.avax.network/ext/bc/C/ws",
				Explorer:   "https://snowtrace.io",
				Currency:   "AVAX",
				Enabled:    true,
				Subnets: []SubnetConfig{
					{
						Name:         "Mainnet",
						ChainID:      "43114",
						VMType:       "EVM",
						NodeURLs:     []string{"https://api.avax.network"},
						WebSocketURL: "wss://api.avax.network/ext/bc/C/ws",
						HTTPURL:      "https://api.avax.network/ext/bc/C/rpc",
						StreamName:   "avalanche-mainnet",
						Subject:      "avalanche.mainnet.blocks",
						Enabled:      true,
						Network:      "Avalanche",
					},
					{
						Name:         "Fuji Testnet",
						ChainID:      "43113",
						VMType:       "EVM",
						NodeURLs:     []string{"https://api.avax-test.network"},
						WebSocketURL: "wss://api.avax-test.network/ext/bc/C/ws",
						HTTPURL:      "https://api.avax-test.network/ext/bc/C/rpc",
						StreamName:   "avalanche-fuji",
						Subject:      "avalanche.fuji.blocks",
						Enabled:      true,
						Network:      "Avalanche",
					},
				},
				Metadata: map[string]string{
					"consensus": "Avalanche",
					"type":      "Layer 1",
				},
			},
			"Ethereum": {
				Name:       "Ethereum",
				ChainID:    "1",
				DefaultRPC: "https://eth.llamarpc.com",
				DefaultWS:  "wss://eth.llamarpc.com",
				Explorer:   "https://etherscan.io",
				Currency:   "ETH",
				Enabled:    true,
				Subnets: []SubnetConfig{
					{
						Name:         "Mainnet",
						ChainID:      "1",
						VMType:       "EVM",
						NodeURLs:     []string{"https://eth.llamarpc.com"},
						WebSocketURL: "wss://eth.llamarpc.com",
						HTTPURL:      "https://eth.llamarpc.com",
						StreamName:   "ethereum-mainnet",
						Subject:      "ethereum.mainnet.blocks",
						Enabled:      true,
						Network:      "Ethereum",
					},
					{
						Name:         "Sepolia Testnet",
						ChainID:      "11155111",
						VMType:       "EVM",
						NodeURLs:     []string{"https://sepolia.infura.io/v3/YOUR_PROJECT_ID"},
						WebSocketURL: "wss://sepolia.infura.io/ws/v3/YOUR_PROJECT_ID",
						HTTPURL:      "https://sepolia.infura.io/v3/YOUR_PROJECT_ID",
						StreamName:   "ethereum-sepolia",
						Subject:      "ethereum.sepolia.blocks",
						Enabled:      false, // Disabled by default - requires API key
						Network:      "Ethereum",
					},
				},
				Metadata: map[string]string{
					"consensus": "Proof of Stake",
					"type":      "Layer 1",
				},
			},
			"Polygon": {
				Name:       "Polygon",
				ChainID:    "137",
				DefaultRPC: "https://polygon-rpc.com",
				DefaultWS:  "wss://polygon-rpc.com",
				Explorer:   "https://polygonscan.com",
				Currency:   "MATIC",
				Enabled:    true,
				Subnets: []SubnetConfig{
					{
						Name:         "Mainnet",
						ChainID:      "137",
						VMType:       "EVM",
						NodeURLs:     []string{"https://polygon-rpc.com"},
						WebSocketURL: "wss://polygon-rpc.com",
						HTTPURL:      "https://polygon-rpc.com",
						StreamName:   "polygon-mainnet",
						Subject:      "polygon.mainnet.blocks",
						Enabled:      true,
						Network:      "Polygon",
					},
					{
						Name:         "Mumbai Testnet",
						ChainID:      "80001",
						VMType:       "EVM",
						NodeURLs:     []string{"https://rpc-mumbai.maticvigil.com"},
						WebSocketURL: "wss://rpc-mumbai.maticvigil.com",
						HTTPURL:      "https://rpc-mumbai.maticvigil.com",
						StreamName:   "polygon-mumbai",
						Subject:      "polygon.mumbai.blocks",
						Enabled:      true,
						Network:      "Polygon",
					},
				},
				Metadata: map[string]string{
					"consensus": "Proof of Stake",
					"type":      "Layer 2",
				},
			},
		},
	}
}

// GetEnabledNetworks returns all enabled networks
func (nr *NetworkRegistry) GetEnabledNetworks() []NetworkConfig {
	var enabled []NetworkConfig
	for _, network := range nr.Networks {
		if network.Enabled {
			enabled = append(enabled, network)
		}
	}
	return enabled
}

// GetEnabledSubnets returns all enabled subnets across all networks
func (nr *NetworkRegistry) GetEnabledSubnets() []SubnetConfig {
	var enabled []SubnetConfig
	for _, network := range nr.Networks {
		if network.Enabled {
			for _, subnet := range network.Subnets {
				if subnet.Enabled {
					enabled = append(enabled, subnet)
				}
			}
		}
	}
	return enabled
}

// GetSubnet returns a specific subnet by network and subnet name
func (nr *NetworkRegistry) GetSubnet(networkName, subnetName string) (*SubnetConfig, error) {
	network, exists := nr.Networks[networkName]
	if !exists {
		return nil, fmt.Errorf("network %s not found", networkName)
	}

	for _, subnet := range network.Subnets {
		if subnet.Name == subnetName {
			return &subnet, nil
		}
	}

	return nil, fmt.Errorf("subnet %s not found in network %s", subnetName, networkName)
}

// GetBucketName generates the MinIO bucket name for a network-subnet combination
func (nr *NetworkRegistry) GetBucketName(networkName, subnetName, bucketPrefix string) string {
	networkClean := strings.ToLower(strings.ReplaceAll(networkName, " ", "-"))
	subnetClean := strings.ToLower(strings.ReplaceAll(subnetName, " ", "-"))
	return fmt.Sprintf("%s-%s-%s", bucketPrefix, networkClean, subnetClean)
}

// AddNetwork adds a new network to the registry
func (nr *NetworkRegistry) AddNetwork(network NetworkConfig) {
	if nr.Networks == nil {
		nr.Networks = make(map[string]NetworkConfig)
	}
	nr.Networks[network.Name] = network
}

// EnableNetwork enables or disables a network
func (nr *NetworkRegistry) EnableNetwork(networkName string, enabled bool) error {
	network, exists := nr.Networks[networkName]
	if !exists {
		return fmt.Errorf("network %s not found", networkName)
	}

	network.Enabled = enabled
	nr.Networks[networkName] = network
	return nil
}

// EnableSubnet enables or disables a subnet
func (nr *NetworkRegistry) EnableSubnet(networkName, subnetName string, enabled bool) error {
	network, exists := nr.Networks[networkName]
	if !exists {
		return fmt.Errorf("network %s not found", networkName)
	}

	for i, subnet := range network.Subnets {
		if subnet.Name == subnetName {
			network.Subnets[i].Enabled = enabled
			nr.Networks[networkName] = network
			return nil
		}
	}

	return fmt.Errorf("subnet %s not found in network %s", subnetName, networkName)
}

// GetNetworkStats returns statistics about the configured networks
func (nr *NetworkRegistry) GetNetworkStats() map[string]interface{} {
	stats := map[string]interface{}{
		"total_networks":      len(nr.Networks),
		"enabled_networks":    0,
		"total_subnets":       0,
		"enabled_subnets":     0,
		"networks_by_type":    make(map[string]int),
		"subnets_by_vm_type":  make(map[string]int),
	}

	for _, network := range nr.Networks {
		if network.Enabled {
			stats["enabled_networks"] = stats["enabled_networks"].(int) + 1
		}

		// Count by type
		networkType := network.Metadata["type"]
		if networkType == "" {
			networkType = "Unknown"
		}
		stats["networks_by_type"].(map[string]int)[networkType]++

		// Count subnets
		stats["total_subnets"] = stats["total_subnets"].(int) + len(network.Subnets)
		for _, subnet := range network.Subnets {
			if subnet.Enabled {
				stats["enabled_subnets"] = stats["enabled_subnets"].(int) + 1
			}
			stats["subnets_by_vm_type"].(map[string]int)[subnet.VMType]++
		}
	}

	return stats
}
