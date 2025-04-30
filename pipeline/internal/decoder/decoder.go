package decoder

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"
)

// Decoder handles transaction decoding using ABI signatures
type Decoder struct {
	cache   Cache
	chainID string
}

// SignatureEntry represents an ABI function signature
type SignatureEntry struct {
	Name   string         `json:"name"`
	Inputs []abi.Argument `json:"inputs"`
}

// NewDecoder creates a new transaction decoder
func NewDecoder(cache Cache, chainID string) *Decoder {
	return &Decoder{
		cache:   cache,
		chainID: chainID,
	}
}

// DecodeTransaction attempts to decode a transaction using cached ABI signatures
func (d *Decoder) DecodeTransaction(ctx context.Context, tx *blockchain.Transaction) error {
	// Skip decoding for contract creation and simple value transfer
	if tx.To == "" || len(tx.Input) == 0 || tx.Input == "0x" {
		return nil
	}

	// Skip if input data too short
	if len(tx.Input) < 10 {
		return fmt.Errorf("input data too short")
	}

	// Extract function selector (first 4 bytes)
	selector := strings.ToLower(tx.Input[:10])
	
	// Try decoding with global selector
	err := d.tryDecode(ctx, tx, selector, "")
	if err == nil {
		return nil
	}

	// Try decoding with contract-specific selector
	if tx.To != "" {
		if err := d.tryDecode(ctx, tx, selector, tx.To); err == nil {
			return nil
		}
	}

	return err
}

// tryDecode attempts to decode a transaction with a specific selector
func (d *Decoder) tryDecode(ctx context.Context, tx *blockchain.Transaction, selector, contractAddr string) error {
	var key string
	if contractAddr != "" {
		key = fmt.Sprintf("sel:%s:%s:%s", d.chainID, strings.ToLower(contractAddr), selector)
	} else {
		key = fmt.Sprintf("sel:%s:%s", d.chainID, selector)
	}

	// Get template from cache or load from file
	template, err := d.cache.GetString(ctx, key)
	if err != nil {
		return fmt.Errorf("signature not found: %w", err)
	}

	var sig SignatureEntry
	if err := json.Unmarshal([]byte(template), &sig); err != nil {
		return fmt.Errorf("invalid signature format: %w", err)
	}

	// Decode input data
	if err := d.decodeCalldata(tx, sig); err != nil {
		return fmt.Errorf("calldata decode failed: %w", err)
	}

	return nil
}

// decodeCalldata decodes the input data using the ABI signature
func (d *Decoder) decodeCalldata(tx *blockchain.Transaction, sig SignatureEntry) error {
	if len(tx.Input) < 10 || len(sig.Inputs) == 0 {
		return fmt.Errorf("invalid input data or signature")
	}

	// Decode input data (skip selector)
	data, err := hex.DecodeString(strings.TrimPrefix(tx.Input[10:], "0x"))
	if err != nil {
		return fmt.Errorf("hex decode failed: %w", err)
	}

	// Create method for unpacking
	method := abi.NewMethod(sig.Name, sig.Name, abi.Function, "", false, false, sig.Inputs, nil)
	
	// Unpack arguments
	args, err := method.Inputs.Unpack(data)
	if err != nil {
		return fmt.Errorf("argument unpack failed: %w", err)
	}

	// Create params map
	params := make(map[string]interface{}, len(sig.Inputs))
	for i, input := range sig.Inputs {
		if input.Type.T == abi.AddressTy {
			if addr, ok := args[i].(common.Address); ok {
				params[input.Name] = strings.ToLower(addr.Hex())
				continue
			}
		}
		params[input.Name] = args[i]
	}

	// Set decoded call
	tx.DecodedCall = &blockchain.DecodedCall{
		Function: sig.Name,
		Params:   params,
	}

	return nil
}
