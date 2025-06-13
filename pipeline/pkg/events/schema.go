package events

import (
	"encoding/json"
	"time"
)

// EventType represents the type of blockchain event
type EventType string

const (
	EventTypeWalletTx     EventType = "wallet_tx"
	EventTypeContractCall EventType = "contract_call"
	EventTypeTokenTransfer EventType = "token_transfer"
	EventTypeNFTTransfer  EventType = "nft_transfer"
	EventTypeStaking      EventType = "staking"
	EventTypeSwap         EventType = "swap"
	EventTypeDefi         EventType = "defi"
)

// EntityType represents the type of entity involved in the event
type EntityType string

const (
	EntityTypeWallet   EntityType = "wallet"
	EntityTypeContract EntityType = "contract"
	EntityTypeToken    EntityType = "token"
	EntityTypeNFT      EntityType = "nft"
	EntityTypePool     EntityType = "pool"
)

// Entity represents the primary entity involved in the event
type Entity struct {
	Type    EntityType `json:"type"`
	Chain   string     `json:"chain"`   // e.g., "avax", "eth", "polygon"
	Address string     `json:"address"` // wallet/contract address
	Name    *string    `json:"name,omitempty"`    // optional human-readable name
	Symbol  *string    `json:"symbol,omitempty"`  // for tokens/contracts
}

// BlockchainEvent represents a standardized blockchain event
type BlockchainEvent struct {
	EventType EventType   `json:"event_type"`
	Entity    Entity      `json:"entity"`
	Timestamp time.Time   `json:"timestamp"`
	TxHash    string      `json:"tx_hash"`
	Details   interface{} `json:"details"` // Flexible nested details
	
	// Metadata for indexing and partitioning
	Metadata EventMetadata `json:"metadata"`
}

// EventMetadata contains indexing and partitioning information
type EventMetadata struct {
	Network     string `json:"network"`      // e.g., "Avalanche", "Ethereum"
	Subnet      string `json:"subnet"`       // e.g., "Mainnet", "Fuji"
	VMType      string `json:"vm_type"`      // e.g., "EVM", "SubnetEVM"
	BlockNumber uint64 `json:"block_number"`
	BlockHash   string `json:"block_hash"`
	TxIndex     uint   `json:"tx_index"`
	
	// Time partitioning fields
	Year  int `json:"year"`
	Month int `json:"month"`
	Day   int `json:"day"`
	Hour  int `json:"hour"`
}

// WalletTxDetails represents details for wallet transaction events
type WalletTxDetails struct {
	From         string  `json:"from"`
	To           *string `json:"to,omitempty"` // null for contract creation
	Value        string  `json:"value"`        // in wei/smallest unit
	Token        string  `json:"token"`        // e.g., "AVAX", "ETH", "USDC"
	TokenAddress *string `json:"token_address,omitempty"` // for ERC20 tokens
	
	// Gas information
	Gas      string `json:"gas"`
	GasPrice string `json:"gas_price"`
	GasUsed  *string `json:"gas_used,omitempty"`
	
	// Transaction metadata
	Nonce    string `json:"nonce"`
	Input    string `json:"input"`
	Status   string `json:"status"` // "confirmed", "failed", "pending"
	
	// Derived information
	TxType      string `json:"tx_type"`      // "send", "receive", "contract_call"
	Direction   string `json:"direction"`    // "in", "out", "self"
	ValueUSD    *string `json:"value_usd,omitempty"`
	DecodedCall *DecodedCall `json:"decoded_call,omitempty"`
}

// TokenTransferDetails represents details for token transfer events
type TokenTransferDetails struct {
	From         string `json:"from"`
	To           string `json:"to"`
	Amount       string `json:"amount"`
	TokenAddress string `json:"token_address"`
	TokenSymbol  string `json:"token_symbol"`
	TokenName    string `json:"token_name"`
	Decimals     uint8  `json:"decimals"`
	
	// Context
	TxHash      string `json:"tx_hash"`
	LogIndex    uint   `json:"log_index"`
	ValueUSD    *string `json:"value_usd,omitempty"`
}

// ContractCallDetails represents details for contract interaction events
type ContractCallDetails struct {
	Contract     string `json:"contract"`
	Function     string `json:"function"`
	Parameters   map[string]interface{} `json:"parameters"`
	ReturnValues map[string]interface{} `json:"return_values,omitempty"`
	
	// Gas and execution info
	Gas      string `json:"gas"`
	GasUsed  string `json:"gas_used"`
	Status   string `json:"status"`
	
	// Decoded information
	DecodedCall *DecodedCall `json:"decoded_call,omitempty"`
}

// DecodedCall represents decoded contract call information
type DecodedCall struct {
	Function   string                 `json:"function"`
	Parameters map[string]interface{} `json:"parameters"`
	Signature  string                 `json:"signature"`
}

// SwapDetails represents details for DEX swap events
type SwapDetails struct {
	Protocol    string `json:"protocol"`    // e.g., "TraderJoe", "Uniswap"
	TokenIn     Token  `json:"token_in"`
	TokenOut    Token  `json:"token_out"`
	AmountIn    string `json:"amount_in"`
	AmountOut   string `json:"amount_out"`
	Fee         string `json:"fee"`
	Slippage    string `json:"slippage"`
	PriceImpact string `json:"price_impact"`
}

// Token represents token information
type Token struct {
	Address  string `json:"address"`
	Symbol   string `json:"symbol"`
	Name     string `json:"name"`
	Decimals uint8  `json:"decimals"`
}

// Helper functions for creating events

// NewWalletTxEvent creates a new wallet transaction event
func NewWalletTxEvent(entity Entity, txHash string, timestamp time.Time, details WalletTxDetails, metadata EventMetadata) BlockchainEvent {
	return BlockchainEvent{
		EventType: EventTypeWalletTx,
		Entity:    entity,
		Timestamp: timestamp,
		TxHash:    txHash,
		Details:   details,
		Metadata:  metadata,
	}
}

// NewTokenTransferEvent creates a new token transfer event
func NewTokenTransferEvent(entity Entity, txHash string, timestamp time.Time, details TokenTransferDetails, metadata EventMetadata) BlockchainEvent {
	return BlockchainEvent{
		EventType: EventTypeTokenTransfer,
		Entity:    entity,
		Timestamp: timestamp,
		TxHash:    txHash,
		Details:   details,
		Metadata:  metadata,
	}
}

// ToJSON converts the event to JSON
func (e BlockchainEvent) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// FromJSON creates an event from JSON
func FromJSON(data []byte) (*BlockchainEvent, error) {
	var event BlockchainEvent
	err := json.Unmarshal(data, &event)
	if err != nil {
		return nil, err
	}
	return &event, nil
}

// GetDetailsAs unmarshals the details into a specific type
func (e BlockchainEvent) GetDetailsAs(target interface{}) error {
	detailsJSON, err := json.Marshal(e.Details)
	if err != nil {
		return err
	}
	return json.Unmarshal(detailsJSON, target)
}
