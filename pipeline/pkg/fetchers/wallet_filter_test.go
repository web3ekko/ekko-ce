package fetchers

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

func TestWalletFiltering(t *testing.T) {
	// Setup test environment with Redis
	ctx := context.Background()

	// Start Redis container
	redisContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "redis:7",
			ExposedPorts: []string{"6379/tcp"},
			WaitingFor:   wait.ForLog("Ready to accept connections"),
		},
		Started: true,
	})
	if err != nil {
		t.Fatalf("Failed to start Redis container: %v", err)
	}
	defer func() {
		if err := redisContainer.Terminate(ctx); err != nil {
			t.Logf("Failed to terminate Redis container: %v", err)
		}
	}()

	// Get Redis connection
	redisHost, err := redisContainer.Host(ctx)
	if err != nil {
		t.Fatalf("Failed to get Redis host: %v", err)
	}
	redisPort, err := redisContainer.MappedPort(ctx, "6379/tcp")
	if err != nil {
		t.Fatalf("Failed to get Redis port: %v", err)
	}

	// Create Redis client and adapter
	rawRedisClient := redis.NewClient(&redis.Options{Addr: redisHost + ":" + redisPort.Port()})
	defer rawRedisClient.Close()

	redisAdapter := decoder.NewRedisClientAdapter(rawRedisClient)

	// Define test data
	whitelistedAddresses := []string{
		"0x123456789abcdef0123456789abcdef012345678",
		"0xfedcba9876543210fedcba9876543210fedcba98",
	}
	
	unwhitelistedAddresses := []string{
		"0xaaaaaa1111111111111111111111111111111111",
		"0xbbbbbb2222222222222222222222222222222222",
	}

	// Add whitelisted addresses to Redis
	redisKey := "wallets:testnet:test:evm"
	for _, addr := range whitelistedAddresses {
		cmd := rawRedisClient.SAdd(ctx, redisKey, addr)
		if err := cmd.Err(); err != nil {
			t.Fatalf("Failed to add wallet to Redis: %v", err)
		}
	}

	// Create test transactions
	transactions := []blockchain.Transaction{
		{
			// Whitelisted 'from', non-whitelisted 'to'
			Hash: "0x1111111111111111111111111111111111111111111111111111111111111111",
			From: whitelistedAddresses[0],
			To:   &unwhitelistedAddresses[0],
		},
		{
			// Non-whitelisted 'from', whitelisted 'to'
			Hash: "0x2222222222222222222222222222222222222222222222222222222222222222",
			From: unwhitelistedAddresses[0],
			To:   &whitelistedAddresses[1],
		},
		{
			// Both non-whitelisted
			Hash: "0x3333333333333333333333333333333333333333333333333333333333333333",
			From: unwhitelistedAddresses[0],
			To:   &unwhitelistedAddresses[1],
		},
		{
			// Both whitelisted
			Hash: "0x4444444444444444444444444444444444444444444444444444444444444444",
			From: whitelistedAddresses[0],
			To:   &whitelistedAddresses[1],
		},
		{
			// Whitelisted 'from', nil 'to' (contract creation)
			Hash: "0x5555555555555555555555555555555555555555555555555555555555555555",
			From: whitelistedAddresses[0],
			To:   nil,
		},
	}

	// Create a minimal BlockFetcher with only what's needed for wallet filtering
	bf := &BlockFetcher{
		nodeConfig: common.NodeConfig{
			Network: "testnet",
			Subnet:  "test",
			VMType:  "evm",
		},
		redisClient:          redisAdapter,
		filterWalletsEnabled: true,
	}

	// Test each transaction with filtering enabled
	t.Run("With filtering enabled", func(t *testing.T) {
		// Should include transactions with whitelisted addresses
		for i, tx := range transactions {
			include, err := bf.shouldIncludeTransaction(ctx, tx)
			
			switch i {
			case 0, 1, 3, 4: // Transactions with whitelisted addresses
				assert.NoError(t, err)
				assert.True(t, include, "Transaction %d with whitelisted address should be included", i)
			case 2: // Transaction with no whitelisted addresses
				assert.NoError(t, err)
				assert.False(t, include, "Transaction %d with no whitelisted addresses should be filtered out", i)
			}
		}
	})

	// Test with filtering disabled
	t.Run("With filtering disabled", func(t *testing.T) {
		bf.filterWalletsEnabled = false
		
		// Should include all transactions
		for i, tx := range transactions {
			include, err := bf.shouldIncludeTransaction(ctx, tx)
			assert.NoError(t, err)
			assert.True(t, include, "Transaction %d should be included when filtering is disabled", i)
		}
	})

	// Test error handling with invalid Redis key - we'll use a special mock adapter for this
	t.Run("With invalid Redis key", func(t *testing.T) {
		// Create a new BlockFetcher with special handling for this test
		specialBf := &BlockFetcher{
			nodeConfig: common.NodeConfig{
				Network: "invalid",
				Subnet:  "test",
				VMType:  "evm",
			},
			// We need a special version of the Redis adapter for this test case
			// that returns an error when SIsMember is called with the invalid key
			redisClient:          &testRedisClientWithError{t: t, innerClient: redisAdapter},
			filterWalletsEnabled: true,
		}
		
		// Should default to including transactions when Redis key is invalid
		tx := blockchain.Transaction{
			Hash: "0x1111111111111111111111111111111111111111111111111111111111111111",
			From: whitelistedAddresses[0],
			To:   &unwhitelistedAddresses[0],
		}
		
		// Now test with our special adapter that simulates an error
		include, err := specialBf.shouldIncludeTransaction(ctx, tx)
		t.Logf("BlockFetcher result with error simulation: include=%v, err=%v", include, err)
		assert.NoError(t, err) // We expect no error because the BlockFetcher should handle Redis errors
		assert.True(t, include, "Transaction should be included when Redis key is invalid")
	})
}

// testRedisClientWithError is a mock Redis client that returns errors for SIsMember when an invalid key pattern is used
type testRedisClientWithError struct {
	innerClient decoder.RedisClient
	t           *testing.T
}

// SIsMember mocks the Redis SISMEMBER command but returns an error for keys with "invalid" in them
func (c *testRedisClientWithError) SIsMember(ctx context.Context, key string, member interface{}) *redis.BoolCmd {
	c.t.Logf("Mock Redis SIsMember called with key: %s", key)
	
	// Simulate an error for the "invalid" key
	if key == "wallets:invalid:test:evm" {
		cmd := redis.NewBoolCmd(ctx)
		cmd.SetErr(errors.New("simulated Redis error: invalid key"))
		return cmd
	}
	
	// Otherwise delegate to the inner client
	return c.innerClient.SIsMember(ctx, key, member)
}

// Implement the rest of RedisClient interface by delegating to the inner client
func (c *testRedisClientWithError) Get(ctx context.Context, key string) *redis.StringCmd {
	return c.innerClient.Get(ctx, key)
}

func (c *testRedisClientWithError) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	return c.innerClient.Set(ctx, key, value, expiration)
}

func (c *testRedisClientWithError) Close() error {
	return c.innerClient.Close()
}
