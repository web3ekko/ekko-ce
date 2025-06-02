package decoder

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
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
	// Skip if already decoded
	if tx.DecodedCall != nil {
		return nil
	}

	toAddress := ""
	if tx.To != nil {
		toAddress = *tx.To
	}

	// Skip if no input data AND not a simple transfer (i.e., To is set but no data)
	if toAddress != "" && tx.Data == "" {
		// This is a simple transfer, already handled by the next block if tx.Data is empty.
		// If tx.Data is truly empty, it will be caught by the "Transfer" case.
		// If toAddress is empty (contract creation), this block is skipped.
	}

	// Handle contract creation: input data is code
	if toAddress == "" && tx.Data != "" { // Contract creation tx.To is nil
		tx.DecodedCall = &blockchain.DecodedCall{
			Function: "contract_creation", // Lowercase to match test expectation
			Params:   map[string]interface{}{"from": tx.From, "init_code": tx.Data, "value": tx.Value}, // Match test expectation
		}
		return nil
	}

	// Handle simple transfer (no input data, toAddress is present)
	if (tx.Data == "" || tx.Data == "0x") && toAddress != "" {
		tx.DecodedCall = &blockchain.DecodedCall{
			Function: "transfer",
			Params:   map[string]interface{}{"from": tx.From, "value": tx.Value, "to": toAddress}, // Add from
		}
		return nil
	}

	// Attempt to decode as a contract call if 'To' is present and there's input data
	if toAddress != "" && len(tx.Data) > 0 {
		// First, try to find a direct match for the method ID (first 4 bytes of input)
		if len(tx.Data) >= 10 && strings.HasPrefix(tx.Data, "0x") { // Ensure it's hex and long enough
			methodID := tx.Data[2:10]
			template, err := d.cache.GetString(ctx, fmt.Sprintf("sel:%s:%s:%s", d.chainID, strings.ToLower(toAddress), methodID))
			if err == nil {
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
		}

		// Fallback to tryDecode which might use ABI of the contract at toAddress
		err := d.tryDecode(ctx, tx, toAddress, tx.Data)
		if err != nil {
			log.Printf("Failed to decode transaction %s input for address %s: %v", tx.Hash, toAddress, err)
			// Even if decoding fails, we can still mark it as a generic contract call
			tx.DecodedCall = &blockchain.DecodedCall{
				Function: "UnknownContractCall",
				Params:   map[string]interface{}{"to": toAddress, "data": tx.Data},
			}
			return err // Or return nil if we want to proceed with the generic call info
		}
		return nil
	}

	// If none of the above, mark as unknown or handle error
	if tx.DecodedCall == nil {
		tx.DecodedCall = &blockchain.DecodedCall{
			Function: "UnknownTransactionType",
			Params:   map[string]interface{}{"data": tx.Data},
		}
	}
	return nil
}

// tryDecode attempts to decode a transaction with a specific selector
func (d *Decoder) tryDecode(ctx context.Context, tx *blockchain.Transaction, contractAddr string, data string) error {
	// Extract function selector (first 4 bytes)
	if len(data) < 10 || !strings.HasPrefix(data, "0x") { // Minimum length for "0x" + 4-byte selector
		return fmt.Errorf("input data too short or not hex for selector extraction: %s", data)
	}
	selector := strings.ToLower(data[2:10]) // Corrected to skip "0x" prefix

	// Try decoding with global selector
	err := d.tryDecodeWithSelector(ctx, tx, selector, "")
	if err == nil {
		return nil
	}

	// Try decoding with contract-specific selector
	if contractAddr != "" {
		if err := d.tryDecodeWithSelector(ctx, tx, selector, contractAddr); err == nil {
			return nil
		}
	}

	return err
}

func (d *Decoder) tryDecodeWithSelector(ctx context.Context, tx *blockchain.Transaction, selector, contractAddr string) error {
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
	if len(tx.Data) < 10 || len(sig.Inputs) == 0 {
		return fmt.Errorf("invalid input data or signature")
	}

	// Decode input data (skip selector)
	data, err := hex.DecodeString(strings.TrimPrefix(tx.Data[10:], "0x"))
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
		switch v := args[i].(type) {
		case common.Address:
			params[input.Name] = strings.ToLower(v.Hex())
		default:
			params[input.Name] = v
		}
	}

	// Set decoded call
	if strings.ToLower(sig.Name) == "transfer" || strings.ToLower(sig.Name) == "transferfrom" { // Common transfer functions
		if _, ok := params["from"]; !ok { // If 'from' is not in ABI args (e.g. standard transfer, not transferFrom)
			params["from"] = strings.ToLower(tx.From) // Use tx.From as the sender
		}
		// Ensure 'to' and 'value' are present if they are part of sig.Inputs, otherwise they are already in params
	}
	tx.DecodedCall = &blockchain.DecodedCall{
		Function: sig.Name,
		Params:   params,
	}

	return nil
}
