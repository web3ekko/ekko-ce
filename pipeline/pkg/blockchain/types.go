package blockchain

// DecodedCall represents a decoded smart contract call
type DecodedCall struct {
	Function string                 `json:"function"`
	Params   map[string]interface{} `json:"params"`
}

// BlockHeader represents a minimal block header for subscription
type BlockHeader struct {
	Hash string `json:"hash"`
}

// JSONRPCRequest represents a JSON-RPC request
type JSONRPCRequest struct {
	JSONRPC string        `json:"jsonrpc"`
	Method  string        `json:"method"`
	Params  []interface{} `json:"params"`
	ID      int           `json:"id"`
}

// JSONRPCResponse represents a JSON-RPC response
type JSONRPCResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	Result  interface{} `json:"result"`
	Error   *struct {
		Code    int    `json:"code"`
		Message string `json:"message"`
	} `json:"error,omitempty"`
	ID int `json:"id"`
}

// Block represents a blockchain block.
type Block struct {
	Hash         string        `json:"hash"`
	ParentHash   string        `json:"parentHash"`
	Number       string        `json:"number"` // Keep as string from JSON, convert to uint64 as needed
	Timestamp    string        `json:"timestamp"` // Keep as string from JSON, convert to uint64 as needed
	Sha3Uncles   string        `json:"sha3Uncles"`
	StateRoot    string        `json:"stateRoot"`
	TransactionsRoot string    `json:"transactionsRoot"`
	ReceiptsRoot string        `json:"receiptsRoot"`
	LogsBloom    string        `json:"logsBloom"`
	Difficulty   string        `json:"difficulty"`
	GasLimit     string        `json:"gasLimit"`
	GasUsed      string        `json:"gasUsed"`
	ExtraData    string        `json:"extraData"`
	Transactions []Transaction `json:"transactions"`
	// Other fields like GasUsed, GasLimit, Miner, etc., can be added here
	// For example, from common.Block (if that's the target structure):
	// BaseFeePerGas    *string       `json:"baseFeePerGas,omitempty"`
	// Difficulty       string        `json:"difficulty"`
	// ExtraData        string        `json:"extraData"`
	// GasLimit         string        `json:"gasLimit"`
	// GasUsed          string        `json:"gasUsed"`
	// LogsBloom        string        `json:"logsBloom"`
	// Miner            string        `json:"miner"`
	// MixHash          *string       `json:"mixHash,omitempty"` // Typically present pre-Merge
	// Nonce            *string       `json:"nonce,omitempty"`   // Can be null post-Merge
	// Sha3Uncles       string        `json:"sha3Uncles"`
	// Size             string        `json:"size"`
	// StateRoot        string        `json:"stateRoot"`
	// TotalDifficulty  string        `json:"totalDifficulty"`
	// ReceiptsRoot     string        `json:"receiptsRoot"` // Added this field
	// Uncles           []string      `json:"uncles"`
	// Withdrawals      []Withdrawal  `json:"withdrawals,omitempty"` // For post-Merge blocks
	// WithdrawalsRoot  *string       `json:"withdrawalsRoot,omitempty"`
}

// Transaction represents a single blockchain transaction.
type Transaction struct {
	Hash             string         `json:"hash"`
	From             string         `json:"from"`
	To               *string        `json:"to"` // Can be null for contract creation
	Value            string         `json:"value"`
	Gas              string         `json:"gas"`      // Keep as string from JSON
	GasPrice         string         `json:"gasPrice"` // Keep as string from JSON
	Nonce            string         `json:"nonce"`    // Keep as string from JSON
	Data             string         `json:"input"`   // Renamed from 'Data' to 'Input' in JSON tag, field name is Data
	DecodedCall      *DecodedCall   `json:"decodedCall,omitempty"`
	BlockHash        *string        `json:"blockHash"`
	BlockNumber      *string        `json:"blockNumber"`
	TransactionIndex *string        `json:"transactionIndex"`
	Type             *string        `json:"type,omitempty"` // EIP-2718 type
	// Add other fields like V, R, S if needed for signature, or from common.Transaction
	// AccessList       []AccessListItem `json:"accessList,omitempty"`
	// ChainID          *string          `json:"chainId,omitempty"`
	// MaxFeePerGas     *string          `json:"maxFeePerGas,omitempty"`
	// MaxPriorityFeePerGas *string      `json:"maxPriorityFeePerGas,omitempty"`
	// V                *string          `json:"v,omitempty"`
	// R                *string          `json:"r,omitempty"`
	// S                *string          `json:"s,omitempty"`
	// YParity          *string          `json:"yParity,omitempty"` // EIP-1559 / EIP-2930
}

// Withdrawal represents a withdrawal in a post-Merge Ethereum block.
// type Withdrawal struct {
// 	Index          string `json:"index"`
// 	ValidatorIndex string `json:"validatorIndex"`
// 	Address        string `json:"address"`
// 	Amount         string `json:"amount"`
// }

// // AccessListItem is part of an EIP-2930 access list.
// type AccessListItem struct {
// 	Address     string   `json:"address"`
// 	StorageKeys []string `json:"storageKeys"`
// }
