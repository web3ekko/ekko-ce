package fetchers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	tcRedis "github.com/testcontainers/testcontainers-go/modules/redis"
	"github.com/testcontainers/testcontainers-go/wait" // Added for wait strategy

	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

// stringPtr is a helper function to get a pointer to a string.
func stringPtr(s string) *string {
	return &s
}

// setupTestEnvironment prepares Redis and NATS containers for testing.
func setupTestEnvironment(t *testing.T) (decoder.RedisClient, *nats.Conn, nats.JetStreamContext, nats.KeyValue, func()) {
	t.Helper()
	ctx := context.Background()

	// Start Redis container
	redisContainer, err := tcRedis.RunContainer(ctx, testcontainers.WithImage("redis:7"))
	require.NoError(t, err, "failed to run redis container")

	redisHost, err := redisContainer.Host(ctx)
	require.NoError(t, err, "failed to get redis host")
	redisPort, err := redisContainer.MappedPort(ctx, "6379/tcp")
	require.NoError(t, err, "failed to get redis mapped port")
	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort.Port())

	redisClientOpts := &redis.Options{Addr: redisAddr}
	appRedisClient := redis.NewClient(redisClientOpts)
	_, err = appRedisClient.Ping(ctx).Result()
	require.NoError(t, err, "failed to ping redis")

	// Start NATS container
	natsReq := testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "nats:2.10-alpine",
			ExposedPorts: []string{"4222/tcp"},
			Cmd:          []string{"-js", "-sd", "/data/jetstream"}, // Enable JetStream and set storage dir
			Tmpfs:        map[string]string{"/data/jetstream": "rw"},    // Provide tmpfs for JetStream
			WaitingFor:   wait.ForLog("Listening for client connections on 0.0.0.0:4222").WithStartupTimeout(10 * time.Second),
		},
		Started: true,
	}
	natsContainer, err := testcontainers.GenericContainer(ctx, natsReq)
	require.NoError(t, err, "failed to run nats container")

	natsHost, err := natsContainer.Host(ctx)
	require.NoError(t, err, "failed to get nats host")
	natsPort, err := natsContainer.MappedPort(ctx, "4222/tcp")
	require.NoError(t, err, "failed to get nats mapped port")
	natsURL := fmt.Sprintf("nats://%s:%s", natsHost, natsPort.Port())


	natsConn, err := nats.Connect(natsURL)
	require.NoError(t, err, "failed to connect to nats")

	js, err := natsConn.JetStream()
	require.NoError(t, err, "failed to get nats jetstream context")

	kvConfig := nats.KeyValueConfig{Bucket: "testKVStoreForBlockFetcher"}
	kvStore, err := js.CreateKeyValue(&kvConfig)
	if err != nil {
		if errors.Is(err, nats.ErrStreamNameAlreadyInUse) {
			kvStore, err = js.KeyValue(kvConfig.Bucket)
			require.NoError(t, err, "failed to bind to existing KeyValue store")
		} else {
			require.NoError(t, err, "failed to create KeyValue store and not an already_exists error")
		}
	}
	require.NotNil(t, kvStore, "kvStore should not be nil")

	cleanupFunc := func() {
		if natsConn != nil {
			natsConn.Close()
		}
		if appRedisClient != nil {
			appRedisClient.Close()
		}
		if natsContainer != nil {
			_ = natsContainer.Terminate(ctx) // Use underscore to ignore error on cleanup if not critical
		}
		if redisContainer != nil {
			_ = redisContainer.Terminate(ctx)
		}
	}

	return appRedisClient, natsConn, js, kvStore, cleanupFunc
}

// mockRPCServer is a helper to create an httptest.Server that mimics a JSON-RPC endpoint.
func mockRPCServer(_ *testing.T, handler http.HandlerFunc) *httptest.Server {
	return httptest.NewServer(handler)
}

func TestFetchFullBlock_SuccessByHash(t *testing.T) {
	blockHash := "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
	expectedBlock := &blockchain.Block{
		Hash:       blockHash,
		Number:     "0x1b4", // Example block number, hex encoded
		ParentHash: "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef12345678", // Corrected length
		Timestamp:  "0x5e4b5c6d", // Example timestamp
		Transactions: []blockchain.Transaction{
			{
				Hash:     "0xtx1",
				From:     "0xfrom1",
				To:       stringPtr("0xto1"),
				Value:    "0x1",
				Gas:      "0x5208",    // 21000
				GasPrice: "0x4a817c800", // 20 Gwei
				Nonce:    "0x0",
				Data:     "0x",
			},
		},
	}

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err, "Failed to decode request in mock server")

		assert.Equal(t, "eth_getBlockByHash", req.Method)
		require.Len(t, req.Params, 2, "Expected 2 params for eth_getBlockByHash")
		assert.Equal(t, blockHash, req.Params[0])
		assert.Equal(t, true, req.Params[1])

		resp := blockchain.JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result:  expectedBlock, // Directly use the block struct, JSON marshaling handles it
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})
	defer server.Close()

	config := ekkoCommon.NodeConfig{
		VMType:   "evm",
		Network:  "testnet",
		// HttpURL: server.URL, // Passed directly to fetchFullBlock
		// WssURL:   "",      // Not used in this test
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t) // js from setupTestEnvironment is ignored for now by NewBlockFetcher
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if config.VMType != "evm" { // NewBlockFetcher only expects redis client for EVM
		bfRedisClient = nil
	}
	nodeCfg := ekkoCommon.NodeConfig{
		ID:      fmt.Sprintf("test-node-%s-%s", config.VMType, config.Network),
		VMType:  config.VMType,
		Network: config.Network,
		Subnet:  "test-subnet",
		HttpURL: server.URL, // Used by ethClient if VMType is EVM
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err, "NewBlockFetcher failed")

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash)

	require.NoError(t, err, "fetchFullBlock returned an error")
	require.NotNil(t, block, "fetchFullBlock returned a nil block")
	assert.Equal(t, expectedBlock.Hash, block.Hash)
	assert.Equal(t, expectedBlock.Number, block.Number)
	assert.Equal(t, expectedBlock.ParentHash, block.ParentHash)
	assert.Equal(t, expectedBlock.Timestamp, block.Timestamp)
	assert.Equal(t, len(expectedBlock.Transactions), len(block.Transactions))
	if len(block.Transactions) > 0 {
		assert.Equal(t, expectedBlock.Transactions[0].Hash, block.Transactions[0].Hash)
	}
}

func TestFetchFullBlock_SuccessByNumber(t *testing.T) {
	blockNumberStr := "0x1b4"
	blockNumberHex := "0x1b4"
	expectedBlockHash := "0xblocknumabcdef1234567890abcdef1234567890abcdef1234567890abcdef"

	expectedBlock := &blockchain.Block{
		Hash:       expectedBlockHash,
		Number:     blockNumberHex,
		ParentHash: "0xdefabc1234567890defabc1234567890defabc1234567890defabc12345678", // Corrected length
		Timestamp:  "0x5e4b5c6d",
		Transactions: []blockchain.Transaction{
			{
				Hash:     "0xtx2",
				From:     "0xfrom2",
				To:       stringPtr("0xto2"),
				Value:    "0x2",
				Gas:      "0x5208",
				GasPrice: "0x4a817c800",
				Nonce:    "0x1",
				Data:     "0x",
			},
		},
	}

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		assert.Equal(t, "eth_getBlockByNumber", req.Method)
		require.Len(t, req.Params, 2)
		assert.Equal(t, blockNumberStr, req.Params[0])
		assert.Equal(t, true, req.Params[1])

		resp := blockchain.JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result:  expectedBlock,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})
	defer server.Close()

	config := ekkoCommon.NodeConfig{VMType: "evm", Network: "testnet" /* HttpURL: server.URL */}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t) // js from setupTestEnvironment is ignored for now by NewBlockFetcher
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if config.VMType != "evm" { // NewBlockFetcher only expects redis client for EVM
		bfRedisClient = nil
	}
	nodeCfg := ekkoCommon.NodeConfig{
		ID:      fmt.Sprintf("test-node-%s-%s", config.VMType, config.Network),
		VMType:  config.VMType,
		Network: config.Network,
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockNumberStr)

	require.NoError(t, err)
	require.NotNil(t, block)
	assert.Equal(t, expectedBlock.Hash, block.Hash)
	assert.Equal(t, expectedBlock.Number, block.Number)
	assert.Equal(t, expectedBlock.ParentHash, block.ParentHash)
	assert.Equal(t, expectedBlock.Timestamp, block.Timestamp)
	assert.Equal(t, len(expectedBlock.Transactions), len(block.Transactions))
	if len(block.Transactions) > 0 {
		assert.Equal(t, expectedBlock.Transactions[0].Hash, block.Transactions[0].Hash)
	}
}

func TestFetchFullBlock_BlockNotFound(t *testing.T) {
	blockHash := "0xdeadbeefcafebabe000000000000000000000000000000000000000000000000"

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		resp := blockchain.JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result:  nil, // Block not found
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})
	defer server.Close()

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-blocknotfound",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t)
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" { // Use nodeCfg
		bfRedisClient = nil
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient) // Pass the full nodeCfg
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash) // server.URL is not passed here

	require.NoError(t, err, "Expected no error when block is not found (nil result)")
	require.Nil(t, block, "Expected nil block when not found")
}

func TestFetchFullBlock_RPCError(t *testing.T) {
	blockHash := "0x123"
	rpcErr := &struct { Code int `json:"code"`; Message string `json:"message"` }{Code: -32000, Message: "Server error"}

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		resp := blockchain.JSONRPCResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   rpcErr,
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	})
	defer server.Close()

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-rpcerror",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t)
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" { // Use nodeCfg
		bfRedisClient = nil
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient) // Pass the full nodeCfg
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash) // server.URL is not passed here

	require.Error(t, err, "Expected an error due to RPC error")
	assert.Nil(t, block, "Expected nil block on RPC error")
	assert.Contains(t, err.Error(), rpcErr.Message, "Error message should contain RPC error message")
}

func TestFetchFullBlock_HTTPError(t *testing.T) {
	blockHash := "0x456"

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintln(w, "Internal Server Error")
	})
	defer server.Close()

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-httperror",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t)
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" { // Use nodeCfg
		bfRedisClient = nil
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient) // Pass the full nodeCfg
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash) // server.URL is not passed here

	require.Error(t, err, "Expected an error due to HTTP error")
	assert.Nil(t, block, "Expected nil block on HTTP error")
	assert.Contains(t, err.Error(), "failed with status 500 Internal Server Error", "Error message mismatch")
}

func TestFetchFullBlock_InvalidIdentifier(t *testing.T) {
	config := ekkoCommon.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: "http://localhost:1234"}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t) // js from setupTestEnvironment is ignored for now by NewBlockFetcher
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if config.VMType != "evm" { // NewBlockFetcher only expects redis client for EVM
		bfRedisClient = nil
	}
	nodeCfg := ekkoCommon.NodeConfig{
		ID:      fmt.Sprintf("test-node-%s-%s", config.VMType, config.Network),
		VMType:  config.VMType,
		Network: config.Network,
		Subnet:  "test-subnet",
		HttpURL: config.HttpURL, // This test case might specifically use config.HttpURL
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, "not_a_hash_or_number")
	require.Error(t, err, "Expected error for invalid block identifier")
	assert.Contains(t, err.Error(), "invalid EVM blockIdentifier format")
}

func TestFetchFullBlock_NonEVMType(t *testing.T) {
	config := ekkoCommon.NodeConfig{VMType: "solana", Network: "devnet", HttpURL: "http://localhost:1234"}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t) // js from setupTestEnvironment is ignored for now by NewBlockFetcher
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if config.VMType != "evm" { // NewBlockFetcher only expects redis client for EVM
		bfRedisClient = nil
	}
	nodeCfg := ekkoCommon.NodeConfig{
		ID:      fmt.Sprintf("test-node-%s-%s", config.VMType, config.Network),
		VMType:  config.VMType,       // This test is specifically for non-EVM
		Network: config.Network,
		Subnet:  "test-subnet",
		HttpURL: config.HttpURL, // For non-EVM, ethClient won't be initialized, URL doesn't matter for ethClient
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, "some_identifier")
	require.Error(t, err, "Expected error for non-EVM vmType")
	assert.Contains(t, err.Error(), "fetchFullBlock not implemented for VMType: solana")
}

func TestFetchFullBlock_EmptyHTTPURL(t *testing.T) {
	config := ekkoCommon.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: ""} // Empty URL
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t) // js from setupTestEnvironment is ignored for now by NewBlockFetcher
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if config.VMType != "evm" { // NewBlockFetcher only expects redis client for EVM
		bfRedisClient = nil
	}
	nodeCfg := ekkoCommon.NodeConfig{
		ID:      fmt.Sprintf("test-node-%s-%s", config.VMType, config.Network),
		VMType:  config.VMType,
		Network: config.Network,
		Subnet:  "test-subnet",
		HttpURL: "", // Test specifically for empty HttpURL
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, "0x123")
	require.Error(t, err, "Expected error for empty HTTP URL")
	assert.Contains(t, err.Error(), "HTTP RPC URL is empty")
}

func TestFetchFullBlock_MalformedJSONResponse(t *testing.T) {
	blockHash := "0x789"

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintln(w, "{not_valid_json]")
	})
	defer server.Close()

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-malformedjsonresponse",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t)
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" { 
		bfRedisClient = nil
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash)

	require.Error(t, err, "Expected an error due to malformed JSON response")
	assert.Nil(t, block, "Expected nil block on malformed JSON response")
	assert.Contains(t, err.Error(), "invalid character 'n' looking for beginning of object key string")
}

func TestFetchFullBlock_Timeout(t *testing.T) {
	blockHash := "0xabc"

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond) // Sleep longer than client timeout
		w.WriteHeader(http.StatusOK)
	})
	defer server.Close()

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-timeout",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	redisC, natsC, _, kv, cleanup := setupTestEnvironment(t)
	defer cleanup()

	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" { 
		bfRedisClient = nil
	}
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient)
	require.NoError(t, err)

	// Temporarily modify client timeout for this specific test case in fetchFullBlock
	// This is tricky because the client is created inside fetchFullBlock.
	// For a real scenario, client might be part of BlockFetcher struct or passed in.
	// Here, we rely on the default 15s timeout in fetchFullBlock being much larger
	// than our artificial delay. To properly test client-side timeout, we'd need to
	// make the HTTP client configurable or use a shorter timeout in the test setup.

	// The current fetchFullBlock has a hardcoded 15s timeout.
	// We can test a server-side timeout by making the server respond very slowly.
	// If the client's timeout (15s) is hit, it should return a context deadline exceeded error.

	// Let's create a context with a shorter timeout for the test itself
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond) // Shorter than server sleep
	defer cancel()

	block, err := bf.fetchFullBlock(ctx, blockHash)

	require.Error(t, err, "Expected an error due to timeout")
	assert.Nil(t, block, "Expected nil block on timeout")
	// Check if the error is a context deadline exceeded error
	// This can manifest in different ways depending on the HTTP client and OS.
	// Often it includes "context deadline exceeded" or "Client.Timeout exceeded".
	assert.True(t, strings.Contains(err.Error(), "context deadline exceeded") || strings.Contains(err.Error(), "Client.Timeout exceeded"),
		"Error message should indicate a timeout: %v", err)
}
