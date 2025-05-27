package fetchers

import (
	"context"
	"encoding/json"
	"github.com/redis/go-redis/v9"
	"github.com/web3ekko/ekko-ce/pipeline/internal/decoder"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
)

// mockRedisClient is a minimal mock for decoder.RedisClient.
type mockRedisClient struct{}

func (m *mockRedisClient) Get(ctx context.Context, key string) *redis.StringCmd {
	// For NewBlockFetcher, it only checks if rc is nil, doesn't call methods for EVM init path relevant to fetchFullBlock tests.
	// If specific Get/Set behavior is needed for other tests, this mock would need expansion.
	return redis.NewStringResult("", nil) // Return a valid StringCmd
}
func (m *mockRedisClient) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	return redis.NewStatusResult("", nil)
}
func (m *mockRedisClient) Close() error { return nil }

// mockRPCServer is a helper to create an httptest.Server that mimics a JSON-RPC endpoint.
func mockRPCServer(t *testing.T, handler http.HandlerFunc) *httptest.Server {
	return httptest.NewServer(handler)
}

func TestFetchFullBlock_SuccessByHash(t *testing.T) {
	blockHash := "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
	expectedBlock := &blockchain.Block{
		Hash: blockHash,
		Transactions: []blockchain.Transaction{
			{Hash: "0xtx1", From: "0xfrom1", To: "0xto1", Value: "0x1"},
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

	config := common.NodeConfig{
		VMType:   "evm",
		Network:  "testnet",
		HttpURL:  server.URL,
		WssURL:   "", // Not used in this test
	}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc) // NATS conn and RedisClient not needed for this unit test
	require.NoError(t, err, "NewBlockFetcher failed")

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

	require.NoError(t, err, "fetchFullBlock returned an error")
	require.NotNil(t, block, "fetchFullBlock returned a nil block")
	assert.Equal(t, expectedBlock.Hash, block.Hash)
	assert.Equal(t, len(expectedBlock.Transactions), len(block.Transactions))
	if len(block.Transactions) > 0 {
		assert.Equal(t, expectedBlock.Transactions[0].Hash, block.Transactions[0].Hash)
	}
}

func TestFetchFullBlock_SuccessByNumber(t *testing.T) {
	blockNumber := "0x1b4"
	expectedBlock := &blockchain.Block{
		Hash: "0xabc", // A different hash for the block found by number
		Transactions: []blockchain.Transaction{
			{Hash: "0xtx2", From: "0xfrom2", To: "0xto2", Value: "0x2"},
		},
	}

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		assert.Equal(t, "eth_getBlockByNumber", req.Method)
		require.Len(t, req.Params, 2)
		assert.Equal(t, blockNumber, req.Params[0])
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

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockNumber)

	require.NoError(t, err)
	require.NotNil(t, block)
	assert.Equal(t, expectedBlock.Hash, block.Hash)
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

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

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

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

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

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

	require.Error(t, err, "Expected an error due to HTTP error")
	assert.Nil(t, block, "Expected nil block on HTTP error")
	assert.Contains(t, err.Error(), "failed with status 500 Internal Server Error", "Error message mismatch")
}

func TestFetchFullBlock_InvalidIdentifier(t *testing.T) {
	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: "http://localhost:1234"}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, config.HttpURL, "not_a_hash_or_number")
	require.Error(t, err, "Expected error for invalid block identifier")
	assert.Contains(t, err.Error(), "invalid EVM blockIdentifier format")
}

func TestFetchFullBlock_NonEVMType(t *testing.T) {
	config := common.NodeConfig{VMType: "solana", Network: "devnet", HttpURL: "http://localhost:1234"}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, config.HttpURL, "some_identifier")
	require.Error(t, err, "Expected error for non-EVM vmType")
	assert.Contains(t, err.Error(), "fetchFullBlock not implemented for VMType: solana")
}

func TestFetchFullBlock_EmptyHTTPURL(t *testing.T) {
	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: ""} // Empty URL
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	_, err = bf.fetchFullBlock(ctx, "", "0x123")
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

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

	require.Error(t, err, "Expected an error due to malformed JSON response")
	assert.Nil(t, block, "Expected nil block on malformed JSON response")
	assert.Contains(t, err.Error(), "failed to decode JSON-RPC response")
}

func TestFetchFullBlock_Timeout(t *testing.T) {
	blockHash := "0xabc"

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond) // Sleep longer than client timeout
		w.WriteHeader(http.StatusOK)
	})
	defer server.Close()

	config := common.NodeConfig{VMType: "evm", Network: "testnet", HttpURL: server.URL}
	var rc decoder.RedisClient
	if config.VMType == "evm" {
		rc = &mockRedisClient{}
	}
	bf, err := NewBlockFetcher(config.VMType, config.Network, nil, nil, rc)
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

	block, err := bf.fetchFullBlock(ctx, server.URL, blockHash)

	require.Error(t, err, "Expected an error due to timeout")
	assert.Nil(t, block, "Expected nil block on timeout")
	// Check if the error is a context deadline exceeded error
	// This can manifest in different ways depending on the HTTP client and OS.
	// Often it includes "context deadline exceeded" or "Client.Timeout exceeded".
	assert.True(t, strings.Contains(err.Error(), "context deadline exceeded") || strings.Contains(err.Error(), "Client.Timeout exceeded"),
		"Error message should indicate a timeout: %v", err)
}
