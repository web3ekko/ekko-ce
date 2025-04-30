package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// SubnetConfig holds configuration for an Avalanche subnet
type SubnetConfig struct {
	Name         string            // Subnet name (e.g., "mainnet", "fuji", "wagmi")
	ChainID      string            // Chain ID for the subnet
	VMType       string            // VM type (e.g., "evm", "subnet-evm")
	NodeURLs     []string          // List of node URLs for redundancy
	PulsarTopic  string            // Pulsar topic for this subnet
	CustomParams map[string]string // Additional subnet-specific parameters
}

// NodeEndpoints represents WebSocket and HTTP endpoints for a node
type NodeEndpoints struct {
	WebSocket string
	HTTP      string
}

// Config holds the application configuration
type Config struct {
	// Network type (e.g., "mainnet", "testnet")
	NetworkType string

	// Base Avalanche node configuration
	BaseNodeURLs []string

	// Subnet configurations
	Subnets []SubnetConfig

	// Pulsar configuration
	PulsarURL string

	// Cache configuration
	CacheType string // "memory" or "redis"
	RedisURL  string

	// Processing configuration
	DecoderWorkers int

	// Retry configuration
	MaxRetries     int
	RetryDelay     time.Duration
	RequestTimeout time.Duration
}

// LoadFromEnv loads configuration from environment variables
func LoadFromEnv() (*Config, error) {
	// Load network type
	networkType := getEnvWithDefault("AVAX_NETWORK", "mainnet")

	// Load base node URLs
	baseNodesStr := os.Getenv("AVAX_BASE_NODES")
	if baseNodesStr == "" {
		return nil, fmt.Errorf("AVAX_BASE_NODES is required (comma-separated list of node URLs)")
	}
	baseNodes := strings.Split(baseNodesStr, ",")

	// Load subnet configurations
	subnetsStr := os.Getenv("AVAX_SUBNETS")
	if subnetsStr == "" {
		return nil, fmt.Errorf("AVAX_SUBNETS is required (comma-separated list of subnet names)")
	}

	subnetNames := strings.Split(subnetsStr, ",")
	subnets := make([]SubnetConfig, 0, len(subnetNames))

	for _, name := range subnetNames {
		name = strings.TrimSpace(name)
		prefix := "AVAX_" + strings.ToUpper(name)

		// Required parameters
		chainID := os.Getenv(prefix + "_CHAIN_ID")
		if chainID == "" {
			return nil, fmt.Errorf("%s_CHAIN_ID is required", prefix)
		}

		vmType := getEnvWithDefault(prefix+"_VM_TYPE", "subnet-evm")

		// Optional subnet-specific nodes
		var nodeURLs []string
		if nodes := os.Getenv(prefix + "_NODES"); nodes != "" {
			nodeURLs = strings.Split(nodes, ",")
		}

		// Custom parameters
		customParams := make(map[string]string)
		if paramsStr := os.Getenv(prefix + "_PARAMS"); paramsStr != "" {
			params := strings.Split(paramsStr, ",")
			for _, param := range params {
				parts := strings.SplitN(param, "=", 2)
				if len(parts) == 2 {
					customParams[parts[0]] = parts[1]
				}
			}
		}

		pulsarTopic := getEnvWithDefault(prefix+"_PULSAR_TOPIC", name+"_transactions")

		subnets = append(subnets, SubnetConfig{
			Name:         name,
			ChainID:      chainID,
			VMType:       vmType,
			NodeURLs:     nodeURLs,
			PulsarTopic:  pulsarTopic,
			CustomParams: customParams,
		})
	}

	// Load other configurations
	pulsarURL := os.Getenv("PULSAR_URL")
	if pulsarURL == "" {
		return nil, fmt.Errorf("PULSAR_URL is required")
	}

	cacheType := getEnvWithDefault("CACHE_TYPE", "memory")
	redisURL := getEnvWithDefault("REDIS_URL", "localhost:6379")
	decoderWorkers := getEnvAsInt("DECODER_WORKERS", 4)

	// Load retry configuration
	maxRetries := getEnvAsInt("MAX_RETRIES", 3)
	retryDelay := getEnvAsDuration("RETRY_DELAY", 5*time.Second)
	requestTimeout := getEnvAsDuration("REQUEST_TIMEOUT", 10*time.Second)

	return &Config{
		NetworkType:    networkType,
		BaseNodeURLs:   baseNodes,
		Subnets:        subnets,
		PulsarURL:      pulsarURL,
		CacheType:      cacheType,
		RedisURL:       redisURL,
		DecoderWorkers: decoderWorkers,
		MaxRetries:     maxRetries,
		RetryDelay:     retryDelay,
		RequestTimeout: requestTimeout,
	}, nil
}

// getEnvWithDefault returns environment variable value or default if not set
func getEnvWithDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// getEnvAsInt returns environment variable as integer or default if not set
func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if i, err := strconv.Atoi(value); err == nil {
			return i
		}
	}
	return defaultValue
}

// getEnvAsDuration returns environment variable as duration or default if not set
func getEnvAsDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if d, err := time.ParseDuration(value); err == nil {
			return d
		}
	}
	return defaultValue
}
