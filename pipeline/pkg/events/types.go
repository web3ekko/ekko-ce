package events

import (
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
)

// ProcessedTransactionEvent represents a transaction that has been fetched,
// decoded (if applicable), and enriched with block context.
// This is the event published by BlockFetcher and consumed by downstream services.
type ProcessedTransactionEvent struct {
	Network        string                     `json:"network"`
	Subnet         string                     `json:"subnet"`
	VMType         string                     `json:"vm_type"`
	BlockHash      string                     `json:"block_hash"`
	BlockNumber    uint64                     `json:"block_number"`
	BlockTimestamp uint64                     `json:"block_timestamp"`    // Unix timestamp (seconds)
	Transaction    *blockchain.Transaction    `json:"transaction"`        // The original transaction
	DecodedCall    *blockchain.DecodedCall    `json:"decoded_call,omitempty"` // Populated by EVM decoder
	EventID        string                     `json:"event_id"`           // Unique ID for this event, typically transaction hash
}
