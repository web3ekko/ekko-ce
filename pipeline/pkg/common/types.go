package common

// NodeConfig mirrors the structure of the node configuration as stored in NATS KV.
// It should be kept in sync with the relevant fields from api/app/models.py:Node
type NodeConfig struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Network     string `json:"network"` // e.g., "Avalanche", "Ethereum"
	Subnet      string `json:"subnet"`  // e.g., "C-Chain", "Fuji", "Sepolia"
	VMType      string `json:"vm_type"` // e.g., "evm", "solana"
	HttpURL     string `json:"http_url"`
	WssURL      string `json:"wss_url,omitempty"` // Added omitempty
	IsEnabled   bool   `json:"is_enabled"`
	Description string `json:"description,omitempty"`
	Status           string `json:"status,omitempty"`            // e.g., NodeStatusActive, NodeStatusUnhealthy
	LastStatusUpdate string `json:"last_status_update,omitempty"` // ISO 8601 timestamp
	LastError        string `json:"last_error,omitempty"`         // Last error message if status is Unhealthy or Error
}

// NodeStatus constants
const (
	NodeStatusUnknown   = "Unknown"   // Default or initial state
	NodeStatusPending   = "Pending"   // Configured, but supervisor hasn't processed it fully yet or first health check pending
	NodeStatusActive    = "Active"    // Connected and actively being used by a pipeline
	NodeStatusUnhealthy = "Unhealthy" // Connection attempts failed, or stream interrupted, may recover
	NodeStatusError     = "Error"     // Persistent error state after retries, requires intervention
	NodeStatusStale     = "Stale"     // Was previously active but is no longer the primary for a pipeline
	// NodeStatusDisabled is implicitly handled by IsEnabled = false
)

// NewHeadEvent represents a new block head detected by a HeadSource.
// This is the event that ManagedPipeline will publish to NATS.
// The BlockFetcher service will subscribe to these events.
type NewHeadEvent struct {
	Hash       string `json:"hash"`
	Number     uint64 `json:"number"`
	Timestamp  uint64 `json:"timestamp"`
	ParentHash string `json:"parentHash"`
	NodeID     string `json:"nodeId"` // ID of the node that reported this head
}
