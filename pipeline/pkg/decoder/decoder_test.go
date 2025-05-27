package decoder_test

import (
	"context"
	"math/big"
	"strings"
	"testing"

	"github.com/go-redis/redismock/v9"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

func TestDecoder_DecodeTransaction(t *testing.T) {
	// Create mock Redis client using redismock
	db, mock := redismock.NewClientMock()

	// Create a Redis adapter with the mock client
	redisAdapter := decoder.NewRedisAdapter(db)
	d := decoder.NewDecoder(redisAdapter, "testchain")

	// Store signatures in mock Redis
	transferSelector := "0xa9059cbb" // transfer(address,uint256) with 0x prefix
	globalKey := "sel:testchain:" + transferSelector
	// JSON template with simple string types
	transferTemplate := `{"name":"transfer","inputs":[{"name":"recipient","type":"address"},{"name":"amount","type":"uint256"}]}`
	// For valid transfer - first try global selector
	mock.ExpectGet(globalKey).SetVal(transferTemplate)

	// For unknown selector - first global lookup
	mock.ExpectGet("sel:testchain:0xdeadbeef").SetErr(redis.Nil)
	// Then contract-specific lookup
	mock.ExpectGet("sel:testchain:0x1234567890123456789012345678901234567890:0xdeadbeef").SetErr(redis.Nil)

	// For invalid input - first global lookup
	mock.ExpectGet("sel:testchain:0x1234").SetErr(redis.Nil)
	// Then contract-specific lookup
	mock.ExpectGet("sel:testchain:0xb794f5ea0ba39494ce839613fffba74279579268:0x1234").SetErr(redis.Nil)

	tests := []struct {
		name     string
		tx       *blockchain.Transaction
		wantErr  bool
		wantFunc string
		wantArgs map[string]interface{}
	}{
		{
			name: "valid transfer transaction",
			tx: &blockchain.Transaction{
				To:    "0x1234567890123456789012345678901234567890", // Add a To address
				Input: "0xa9059cbb000000000000000000000000b794f5ea0ba39494ce839613fffba74279579268000000000000000000000000000000000000000000000000000000000000000a",
			},
			wantErr:  false,
			wantFunc: "transfer",
			wantArgs: map[string]interface{}{
				"recipient": "0xb794f5ea0ba39494ce839613fffba74279579268",
				"amount":    big.NewInt(10),
			},
		},
		{
			name: "contract creation",
			tx: &blockchain.Transaction{
				To:    "", // Empty To address indicates contract creation
				Input: "0x608060405234801561001057600080fd5b50610150806100206000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c806317d7de7c1461003b578063c47f0027146100b9575b600080fd5b61004361011a565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561008357808201518184015260208101905061006857565b50505050905090810190601f1680156100b05780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b610118600480360360208110156100cf57600080fd5b81019080803590602001906401000000008111156100ec57600080fd5b8201836020820111156100fe57600080fd5b8035906020019184600183028401116401000000008311171561012057600080fd5b90919293919293905050505061015c565b005b60008054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156101545780601f1061012957610100808354040283529160200191610154565b820191906000526020600020905b81548152906001019060200180831161013757829003601f168201915b505050505081565b8282826000919061016d92919061017b565b505050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f106101bc57803560ff19168380011785556101ea565b828001600101855582156101ea579182015b828111156101e95782358255916020019190600101906101ce565b5b5090506101f791906101fb565b5090565b61021d91905b80821115610219576000816000905550600101610201565b5090565b9056fea265627a7a723058204b651e0d8c75664a21f5e8d643a0a6a2d197c1a6824721d51b7c5e23e4e4747364736f6c634300050a0032",
				Value: "0x0",
			},
			wantErr: false, // Contract creation should not be considered an error
			wantFunc: "contract_creation",
			wantArgs: map[string]interface{}{
				"from":      "", // Assuming tx.From is empty or not set in test
				"init_code": "0x608060405234801561001057600080fd5b50610150806100206000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c806317d7de7c1461003b578063c47f0027146100b9575b600080fd5b61004361011a565b6040518080602001828103825283818151815260200191508051906020019080838360005b8381101561008357808201518184015260208101905061006857565b50505050905090810190601f1680156100b05780820380516001836020036101000a031916815260200191505b509250505060405180910390f35b610118600480360360208110156100cf57600080fd5b81019080803590602001906401000000008111156100ec57600080fd5b8201836020820111156100fe57600080fd5b8035906020019184600183028401116401000000008311171561012057600080fd5b90919293919293905050505061015c565b005b60008054600181600116156101000203166002900480601f0160208091040260200160405190810160405280929190818152602001828054600181600116156101000203166002900480156101545780601f1061012957610100808354040283529160200191610154565b820191906000526020600020905b81548152906001019060200180831161013757829003601f168201915b505050505081565b8282826000919061016d92919061017b565b505050565b828054600181600116156101000203166002900490600052602060002090601f016020900481019282601f106101bc57803560ff19168380011785556101ea565b828001600101855582156101ea579182015b828111156101e95782358255916020019190600101906101ce565b5b5090506101f791906101fb565b5090565b61021d91905b80821115610219576000816000905550600101610201565b5090565b9056fea265627a7a723058204b651e0d8c75664a21f5e8d643a0a6a2d197c1a6824721d51b7c5e23e4e4747364736f6c634300050a0032",
				"value":     "0x0",
			},
		},
		{
			name: "simple value transfer",
			tx: &blockchain.Transaction{
				To:    "0xb794f5ea0ba39494ce839613fffba74279579268",
				Input: "0x",                // Empty input data for simple value transfer
				Value: "0xde0b6b3a7640000", // 1 AVAX in hex
			},
			wantErr: false, // Simple value transfer should not be considered an error
			wantFunc: "transfer",
			wantArgs: map[string]interface{}{
				"from":  "", // Assuming tx.From is empty or not set in test
				"to":    "0xb794f5ea0ba39494ce839613fffba74279579268",
				"value": "0xde0b6b3a7640000",
			},
		},
		{
			name: "invalid input data",
			tx: &blockchain.Transaction{
				To:    "0xb794f5ea0ba39494ce839613fffba74279579268",
				Input: "0x1234",
			},
			wantErr: true,
		},
		{
			name: "unknown selector",
			tx: &blockchain.Transaction{
				To:    "0x1234567890123456789012345678901234567890",
				Input: "0xdeadbeef000000000000000000000000000000000000000000000000000000000000000a",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := d.DecodeTransaction(context.Background(), tt.tx)
			if tt.wantErr {
				assert.Error(t, err)
				return
			}

			require.NoError(t, err)
			if tt.wantFunc != "" {
				require.NotNil(t, tt.tx.DecodedCall)
				assert.Equal(t, tt.wantFunc, tt.tx.DecodedCall.Function)
				assert.Equal(t, tt.wantArgs, tt.tx.DecodedCall.Params)
			} else {
				assert.Nil(t, tt.tx.DecodedCall)
			}
		})
	}
}

func TestDecoder_ContractSpecificSelector(t *testing.T) {
	// Create mock Redis client using redismock
	db, mock := redismock.NewClientMock()

	// Create a Redis adapter with the mock client
	redisAdapter := decoder.NewRedisAdapter(db)
	d := decoder.NewDecoder(redisAdapter, "testchain")

	// Prepare signature lookup expectations
	selector := "0xa9059cbb"
	// Global lookup fails
	globalKey := "sel:testchain:" + selector
	mock.ExpectGet(globalKey).SetErr(redis.Nil)

	// Contract-specific lookup succeeds with customTransfer template
	contractAddr := "0x1234567890123456789012345678901234567890"
	key := "sel:testchain:" + strings.ToLower(contractAddr) + ":" + selector
	customTemplate := `{"name":"customTransfer","inputs":[{"name":"amount","type":"uint256"}]}`
	mock.ExpectGet(key).SetVal(customTemplate)

	// Test contract-specific selector
	tx := &blockchain.Transaction{
		To:    contractAddr,
		Input: "0xa9059cbb000000000000000000000000000000000000000000000000000000000000000a",
	}

	err := d.DecodeTransaction(context.Background(), tx)
	require.NoError(t, err)
	require.NotNil(t, tx.DecodedCall)
	assert.Equal(t, "customTransfer", tx.DecodedCall.Function)
	assert.Equal(t, map[string]interface{}{
		"amount": big.NewInt(10),
	}, tx.DecodedCall.Params)
}
