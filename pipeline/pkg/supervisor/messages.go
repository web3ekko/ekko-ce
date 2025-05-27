package supervisor

import "github.com/web3ekko/ekko-ce/pipeline/internal/blockchain"

// NewHeadPayload is the message published by NewHeadListener
// when a new block head is detected via WebSocket.
type NewHeadPayload struct {
	Network     string `json:"network"`
	NodeID      string `json:"node_id"`
	VMType      string `json:"vm_type"`
	BlockHash   string `json:"block_hash"`
	BlockNumber uint64 `json:"block_number"`
	HttpURL     string `json:"http_url"`
}

// FetchedBlockPayload is the message published by BlockFetcher
// after it has retrieved and processed a block.
type FetchedBlockPayload struct {
	Network      string                   `json:"network"`
	BlockHash    string                   `json:"block_hash"`
	BlockNumber  uint64                   `json:"block_number"`
	Transactions []*blockchain.Transaction `json:"transactions"`
}
