package common

// NodeConfig mirrors the structure of the node configuration as stored in NATS KV.
// It should be kept in sync with the relevant fields from api/app/models.py:Node
type NodeConfig struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Network     string `json:"network"` // e.g., "mainnet", "sepolia"
	VMType      string `json:"vm_type"` // e.g., "evm", "solana"
	HttpURL     string `json:"http_url"`
	WssURL      string `json:"wss_url"`
	IsEnabled   bool   `json:"is_enabled"`
	Description string `json:"description,omitempty"`
	// Add other fields from api/app/models.py:Node as needed
}
