package events

import (
	"fmt"
	"strings"
	"time"

	"github.com/ekko-ce/pipeline/pkg/blockchain"
)

// TransactionToEventConverter converts blockchain transactions to standardized events
type TransactionToEventConverter struct {
	// Configuration for conversion
	defaultChain string
	chainMapping map[string]string // network -> chain mapping
}

// NewTransactionToEventConverter creates a new converter
func NewTransactionToEventConverter(defaultChain string) *TransactionToEventConverter {
	return &TransactionToEventConverter{
		defaultChain: defaultChain,
		chainMapping: map[string]string{
			"Avalanche": "avax",
			"Ethereum":  "eth",
			"Polygon":   "polygon",
			"BSC":       "bsc",
		},
	}
}

// ConvertTransaction converts a blockchain transaction to one or more events
func (c *TransactionToEventConverter) ConvertTransaction(
	tx blockchain.Transaction,
	network, subnet, vmType string,
	blockNumber uint64,
	blockHash string,
	txIndex uint,
	blockTime time.Time,
) ([]BlockchainEvent, error) {

	var events []BlockchainEvent

	// Get chain identifier
	chain := c.getChainFromNetwork(network)

	// Create metadata
	metadata := EventMetadata{
		Network:     network,
		Subnet:      subnet,
		VMType:      vmType,
		BlockNumber: blockNumber,
		BlockHash:   blockHash,
		TxIndex:     txIndex,
		Year:        blockTime.Year(),
		Month:       int(blockTime.Month()),
		Day:         blockTime.Day(),
		Hour:        blockTime.Hour(),
	}

	// Create primary wallet transaction event for the sender
	fromEvent, err := c.createWalletTxEvent(tx, chain, "from", blockTime, metadata)
	if err != nil {
		return nil, fmt.Errorf("failed to create from event: %w", err)
	}
	events = append(events, fromEvent)

	// Create wallet transaction event for the receiver (if different from sender)
	if tx.To != nil && strings.ToLower(*tx.To) != strings.ToLower(tx.From) {
		toEvent, err := c.createWalletTxEvent(tx, chain, "to", blockTime, metadata)
		if err != nil {
			return nil, fmt.Errorf("failed to create to event: %w", err)
		}
		events = append(events, toEvent)
	}

	// If this is a token transfer, create additional token transfer events
	if c.isTokenTransfer(tx) {
		tokenEvents, err := c.createTokenTransferEvents(tx, chain, blockTime, metadata)
		if err != nil {
			return nil, fmt.Errorf("failed to create token events: %w", err)
		}
		events = append(events, tokenEvents...)
	}

	// If this is a contract interaction, create contract call event
	if c.isContractInteraction(tx) {
		contractEvent, err := c.createContractCallEvent(tx, chain, blockTime, metadata)
		if err != nil {
			return nil, fmt.Errorf("failed to create contract event: %w", err)
		}
		events = append(events, contractEvent)
	}

	return events, nil
}

// createWalletTxEvent creates a wallet transaction event
func (c *TransactionToEventConverter) createWalletTxEvent(
	tx blockchain.Transaction,
	chain, perspective string,
	blockTime time.Time,
	metadata EventMetadata,
) (BlockchainEvent, error) {

	// Determine the wallet address based on perspective
	var walletAddress string
	var direction string

	switch perspective {
	case "from":
		walletAddress = tx.From
		direction = "out"
	case "to":
		if tx.To == nil {
			return BlockchainEvent{}, fmt.Errorf("cannot create 'to' event for contract creation")
		}
		walletAddress = *tx.To
		direction = "in"
	default:
		return BlockchainEvent{}, fmt.Errorf("invalid perspective: %s", perspective)
	}

	// Create entity
	entity := Entity{
		Type:    EntityTypeWallet,
		Chain:   chain,
		Address: walletAddress,
	}

	// Determine transaction type
	txType := c.determineTxType(tx, perspective)

	// Determine token symbol
	tokenSymbol := c.getTokenSymbol(chain)

	// Create details
	details := WalletTxDetails{
		From:      tx.From,
		To:        tx.To,
		Value:     tx.Value,
		Token:     tokenSymbol,
		Gas:       tx.Gas,
		GasPrice:  tx.GasPrice,
		Nonce:     tx.Nonce,
		Input:     tx.Data,
		Status:    "confirmed", // Default to confirmed
		TxType:    txType,
		Direction: direction,
	}

	// Add decoded call if available
	if tx.DecodedCall != nil {
		details.DecodedCall = &DecodedCall{
			Function:   tx.DecodedCall.Function,
			Parameters: tx.DecodedCall.Params,
			Signature:  tx.DecodedCall.Function, // Use function name as signature for now
		}
	}

	return NewWalletTxEvent(entity, tx.Hash, blockTime, details, metadata), nil
}

// createTokenTransferEvents creates token transfer events
func (c *TransactionToEventConverter) createTokenTransferEvents(
	tx blockchain.Transaction,
	chain string,
	blockTime time.Time,
	metadata EventMetadata,
) ([]BlockchainEvent, error) {

	var events []BlockchainEvent

	// If this looks like an ERC20 transfer based on decoded call
	if tx.DecodedCall != nil && tx.DecodedCall.Function == "transfer" {
		// Extract token transfer details from decoded call
		if to, ok := tx.DecodedCall.Params["to"].(string); ok {
			if amount, ok := tx.DecodedCall.Params["value"].(string); ok {

				// Create entity for the token contract
				entity := Entity{
					Type:    EntityTypeToken,
					Chain:   chain,
					Address: *tx.To, // Contract address
				}

				details := TokenTransferDetails{
					From:         tx.From,
					To:           to,
					Amount:       amount,
					TokenAddress: *tx.To,
					TokenSymbol:  "UNKNOWN", // Would need to look up
					TokenName:    "Unknown Token",
					Decimals:     18, // Default
					TxHash:       tx.Hash,
					LogIndex:     0, // Would need to parse from logs
				}

				event := NewTokenTransferEvent(entity, tx.Hash, blockTime, details, metadata)
				events = append(events, event)
			}
		}
	}

	return events, nil
}

// createContractCallEvent creates a contract interaction event
func (c *TransactionToEventConverter) createContractCallEvent(
	tx blockchain.Transaction,
	chain string,
	blockTime time.Time,
	metadata EventMetadata,
) (BlockchainEvent, error) {

	if tx.To == nil {
		return BlockchainEvent{}, fmt.Errorf("contract creation not supported yet")
	}

	// Create entity for the contract
	entity := Entity{
		Type:    EntityTypeContract,
		Chain:   chain,
		Address: *tx.To,
	}

	// Create details
	details := ContractCallDetails{
		Contract:   *tx.To,
		Function:   "unknown",
		Parameters: make(map[string]interface{}),
		Gas:        tx.Gas,
		Status:     "confirmed",
	}

	// Add decoded call information if available
	if tx.DecodedCall != nil {
		details.Function = tx.DecodedCall.Function
		details.Parameters = tx.DecodedCall.Params
		details.DecodedCall = &DecodedCall{
			Function:   tx.DecodedCall.Function,
			Parameters: tx.DecodedCall.Params,
			Signature:  tx.DecodedCall.Function,
		}
	}

	event := BlockchainEvent{
		EventType: EventTypeContractCall,
		Entity:    entity,
		Timestamp: blockTime,
		TxHash:    tx.Hash,
		Details:   details,
		Metadata:  metadata,
	}

	return event, nil
}

// Helper functions

func (c *TransactionToEventConverter) getChainFromNetwork(network string) string {
	if chain, ok := c.chainMapping[network]; ok {
		return chain
	}
	return strings.ToLower(network)
}

func (c *TransactionToEventConverter) determineTxType(tx blockchain.Transaction, perspective string) string {
	if tx.To == nil {
		return "contract_creation"
	}

	if tx.Data != "" && tx.Data != "0x" {
		return "contract_call"
	}

	if perspective == "from" {
		return "send"
	}
	return "receive"
}

func (c *TransactionToEventConverter) getTokenSymbol(chain string) string {
	switch chain {
	case "avax":
		return "AVAX"
	case "eth":
		return "ETH"
	case "polygon":
		return "MATIC"
	case "bsc":
		return "BNB"
	default:
		return "UNKNOWN"
	}
}

func (c *TransactionToEventConverter) isTokenTransfer(tx blockchain.Transaction) bool {
	// Check if this is likely a token transfer
	if tx.DecodedCall != nil {
		function := strings.ToLower(tx.DecodedCall.Function)
		return function == "transfer" || function == "transferfrom"
	}
	return false
}

func (c *TransactionToEventConverter) isContractInteraction(tx blockchain.Transaction) bool {
	// Check if this is a contract interaction
	return tx.To != nil && (tx.Data != "" && tx.Data != "0x")
}
