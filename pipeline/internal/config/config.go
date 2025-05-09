package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// SubnetConfig holds configuration for an Avalanche subnet
type SubnetConfig struct {
	Name         string            `yaml:"name"` // Subnet name (e.g., "mainnet", "fuji", "wagmi")
	Blockchain   string            `yaml:"blockchain,omitempty"`
	ChainID      string            `yaml:"chain_id,omitempty"`
	NodeURLs     []string          `yaml:"nodes"`
	StreamName   string            `yaml:"stream_name,omitempty"`
	Subject      string            `yaml:"subject,omitempty"`
	Templates    map[string]string `yaml:"templates,omitempty"`
	CustomParams map[string]string `yaml:"custom_params,omitempty"`
	WebSocketURL string            `yaml:"websocket_url,omitempty"` // Optional override for WS endpoint
	HTTPURL      string            `yaml:"http_url,omitempty"`      // Optional override for HTTP endpoint
	VMType       string            `yaml:"vm_type,omitempty"`
}

// NodeEndpoints represents WebSocket and HTTP endpoints for a node
type NodeEndpoints struct {
	WebSocket string
	HTTP      string
}

// Config holds the application configuration
type Config struct {
	// Subnets configuration
	Subnets []SubnetConfig `yaml:"subnets"`

	// Redis configuration
	RedisURL string

	// NATS configuration
	NatsURL string

	// Decoder configuration
	DecoderWorkers int
	BatchSize      int

	// Retry configuration
	MaxRetries     int
	RetryDelay     time.Duration
	RequestTimeout time.Duration
	NetworkType    string
	CacheType      string
}

// LoadFromEnv loads configuration from environment variables
func LoadFromEnv() (*Config, error) {
	// Load network type
	networkType := getEnvWithDefault("AVAX_NETWORK", "mainnet")

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

		// Load per-subnet NATS stream and subject
		streamName := os.Getenv(prefix + "_STREAM_NAME")
		subject := os.Getenv(prefix + "_SUBJECT")

		// Optional overrides for RPC URLs
		wsURL := os.Getenv(prefix + "_WEBSOCKET_URL")
		httpURL := os.Getenv(prefix + "_HTTP_URL")

		subnets = append(subnets, SubnetConfig{
			Name:         name,
			ChainID:      chainID,
			VMType:       vmType,
			NodeURLs:     nodeURLs,
			StreamName:   streamName,
			Subject:      subject,
			CustomParams: customParams,
			WebSocketURL: wsURL,
			HTTPURL:      httpURL,
		})
	}
	// Default topic to subnet name if still unset
	for i := range subnets {
		if subnets[i].StreamName == "" {
			subnets[i].StreamName = "BLOCKCHAIN"
		}
		if subnets[i].Subject == "" {
			subnets[i].Subject = subnets[i].Name
		}
	}

	// Load other configurations
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		// Default to localhost if not specified
		natsURL = "nats://localhost:4222"
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
		Subnets:        subnets,
		NatsURL:        natsURL,
		CacheType:      cacheType,
		RedisURL:       redisURL,
		DecoderWorkers: decoderWorkers,
		MaxRetries:     maxRetries,
		RetryDelay:     retryDelay,
		RequestTimeout: requestTimeout,
	}, nil
}

// Load reads a YAML config file (path), falls back to environment loader on error
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return LoadFromEnv()
	}
	var fileCfg struct {
		Subnets []SubnetConfig `yaml:"subnets"`
	}
	if err := yaml.Unmarshal(data, &fileCfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file %s: %w", path, err)
	}
	// Expand env in URLs
	for i := range fileCfg.Subnets {
		sc := &fileCfg.Subnets[i]
		sc.WebSocketURL = os.ExpandEnv(sc.WebSocketURL)
		sc.HTTPURL = os.ExpandEnv(sc.HTTPURL)
	}
	// Load base config (env or defaults) then override subnets entirely from YAML
	cfg, err := LoadFromEnv()
	if err != nil {
		return nil, err
	}
	cfg.Subnets = fileCfg.Subnets
	// Default topic to subnet name if not set in YAML
	for i := range cfg.Subnets {
		if cfg.Subnets[i].StreamName == "" {
			cfg.Subnets[i].StreamName = "BLOCKCHAIN"
		}
		if cfg.Subnets[i].Subject == "" {
			cfg.Subnets[i].Subject = cfg.Subnets[i].Name
		}
	}
	return cfg, nil
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
