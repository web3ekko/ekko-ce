package blockchain

// Block represents an Ethereum-like block with transactions
type Block struct {
	Hash         string        `json:"hash"`
	Transactions []Transaction `json:"transactions"`
}

// Transaction represents an Ethereum-like transaction
type Transaction struct {
	Hash        string      `json:"hash"`
	From        string      `json:"from"`
	To          string      `json:"to"`
	Value       string      `json:"value"`
	Input       string      `json:"input"`
	DecodedCall *DecodedCall `json:"decoded_call,omitempty"`
}

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
	ID      int          `json:"id"`
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
