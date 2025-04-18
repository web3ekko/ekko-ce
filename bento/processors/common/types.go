package common

import "time"

// Transaction represents a blockchain transaction with analysis
type Transaction struct {
	Hash        string    `json:"hash"`
	BlockNumber int64     `json:"block_number"`
	From        string    `json:"from"`
	To          string    `json:"to"`
	Value       string    `json:"value"`
	Data        string    `json:"data"`
	Timestamp   time.Time `json:"timestamp"`
	Chain       string    `json:"chain"`
}

// TokenTransfer represents a token transfer event
type TokenTransfer struct {
	Transaction
	TokenAddress string `json:"token_address"`
	TokenSymbol  string `json:"token_symbol"`
	TokenAmount  string `json:"token_amount"`
	TokenType    string `json:"token_type"` // ERC20, ERC721, etc.
}

// SwapEvent represents a DEX swap event
type SwapEvent struct {
	Transaction
	Protocol     string `json:"protocol"`      // Uniswap, Trader Joe, etc.
	TokenIn      string `json:"token_in"`      // Input token address
	TokenOut     string `json:"token_out"`     // Output token address
	AmountIn     string `json:"amount_in"`     // Input amount
	AmountOut    string `json:"amount_out"`    // Output amount
	TokenInDec   int    `json:"token_in_dec"`  // Input token decimals
	TokenOutDec  int    `json:"token_out_dec"` // Output token decimals
	TokenInSym   string `json:"token_in_sym"`  // Input token symbol
	TokenOutSym  string `json:"token_out_sym"` // Output token symbol
}

// NFTEvent represents an NFT-related event
type NFTEvent struct {
	Transaction
	Collection string `json:"collection"`      // Collection address
	Name       string `json:"name"`           // Collection name
	TokenID    string `json:"token_id"`       // NFT token ID
	EventType  string `json:"event_type"`     // mint, transfer, sale
	Price      string `json:"price"`          // Price if sold
	Currency   string `json:"currency"`       // Currency used for sale
	Platform   string `json:"platform"`       // Platform where event occurred
}

// LendingEvent represents a DeFi lending event
type LendingEvent struct {
	Transaction
	Protocol    string `json:"protocol"`     // Aave, Compound, etc.
	Action      string `json:"action"`       // supply, borrow, repay, withdraw
	Asset       string `json:"asset"`        // Asset address
	AssetSymbol string `json:"asset_symbol"` // Asset symbol
	Amount      string `json:"amount"`       // Amount of asset
	APY         string `json:"apy"`         // Current APY for the asset
}

// ContractEvent represents a smart contract event
type ContractEvent struct {
	Transaction
	EventType    string            `json:"event_type"`    // deploy, upgrade, call
	ContractName string            `json:"contract_name"` // If known
	MethodName   string            `json:"method_name"`   // If known
	Arguments    map[string]string `json:"arguments"`     // Decoded arguments
}
