package fetchers

import (
	"context"
	"encoding/json"
	"net/http"
	"testing"

	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/testutils"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestSharedEnvironment_FetchFullBlock_Success demonstrates a complete working test
// using the shared test environment with correct block fields.
func TestSharedEnvironment_FetchFullBlock_Success(t *testing.T) {
	// Get shared environment
	redisC, natsC, js, err := testutils.GetTestEnvironment(testCtx)
	require.NoError(t, err, "Failed to get test environment")
	
	// Create test-specific KV store
	kv, err := testutils.GetTestKeyValueStore(js, t.Name())
	require.NoError(t, err, "Failed to create KV store")
	
	blockHash := "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
	
	// Define a complete block with all required fields
	expectedBlock := &blockchain.Block{
		Hash:            blockHash,
		Number:          "0x1", 
		ParentHash:      "0x0000000000000000000000000000000000000000000000000000000000000000",
		Sha3Uncles:      "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347",
		StateRoot:       "0x0000000000000000000000000000000000000000000000000000000000000000",
		TransactionsRoot: "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421",
		ReceiptsRoot:    "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421",
		LogsBloom:       "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
		Difficulty:      "0x0",
		GasLimit:        "0x1000000",
		GasUsed:         "0x0",        // Required field
		ExtraData:       "0x",         // Required field
		Timestamp:       "0x2",
		Transactions:    []blockchain.Transaction{},
	}

	server := mockRPCServer(t, func(w http.ResponseWriter, r *http.Request) {
		var req blockchain.JSONRPCRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		assert.Equal(t, "eth_getBlockByHash", req.Method)
		require.Len(t, req.Params, 2)
		assert.Equal(t, blockHash, req.Params[0])
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

	nodeCfg := ekkoCommon.NodeConfig{
		ID:      "test-node-evm-testnet-shared",
		VMType:  "evm",
		Network: "testnet",
		Subnet:  "test-subnet",
		HttpURL: server.URL,
	}
	
	var bfRedisClient decoder.RedisClient = redisC
	if nodeCfg.VMType != "evm" {
		bfRedisClient = nil
	}
	
	bf, err := NewBlockFetcher(nodeCfg, natsC, kv, bfRedisClient, true)
	require.NoError(t, err)

	ctx := context.Background()
	block, err := bf.fetchFullBlock(ctx, blockHash)

	require.NoError(t, err, "fetchFullBlock returned an error")
	require.NotNil(t, block, "fetchFullBlock returned a nil block")
	assert.Equal(t, expectedBlock.Number, block.Number)
	assert.Equal(t, expectedBlock.ParentHash, block.ParentHash)
	assert.Equal(t, expectedBlock.Timestamp, block.Timestamp)
	assert.Equal(t, len(expectedBlock.Transactions), len(block.Transactions))
}
