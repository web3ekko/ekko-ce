package transaction

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/benthosdev/benthos/v4/public/service"
)

// TransactionType represents different types of blockchain transactions
type TransactionType string

const (
	Transfer      TransactionType = "transfer"
	Swap          TransactionType = "swap"
	Approval      TransactionType = "approval"
	SmartContract TransactionType = "smart_contract"
	Unknown       TransactionType = "unknown"
)

// Transaction represents a blockchain transaction with analysis
type Transaction struct {
	Hash        string         `json:"hash"`
	BlockNumber int64          `json:"block_number"`
	From        string         `json:"from"`
	To          string         `json:"to"`
	Value       string         `json:"value"`
	Data        string         `json:"data"`
	Timestamp   time.Time      `json:"timestamp"`
	Type        TransactionType `json:"type"`
	Description string         `json:"description"`
	Chain       string         `json:"chain"`
}

func init() {
	// Register our processor with Benthos
	err := service.RegisterProcessor(
		"analyze_transaction",
		service.NewConfigSpec().
			Summary("Analyzes blockchain transactions and adds type and description fields.").
			Field(service.NewStringField("chain").
				Description("The blockchain network identifier").
				Default("ethereum")),
		func(conf *service.ParsedConfig) (service.Processor, error) {
			chain, err := conf.FieldString("chain")
			if err != nil {
				return nil, err
			}
			return newTransactionProcessor(chain), nil
		})
	if err != nil {
		panic(err)
	}
}

type transactionProcessor struct {
	chain string
}

func newTransactionProcessor(chain string) *transactionProcessor {
	return &transactionProcessor{
		chain: chain,
	}
}

// Process implements the Benthos service.Processor interface
func (p *transactionProcessor) Process(ctx context.Context, msg *service.Message) (service.MessageBatch, error) {
	// Parse the input message
	var tx Transaction
	if err := msg.UnmarshalJSON(&tx); err != nil {
		return nil, fmt.Errorf("failed to parse transaction: %v", err)
	}

	// Set chain and timestamp
	tx.Chain = p.chain
	tx.Timestamp = time.Now()

	// Analyze the transaction
	if err := p.analyzeTransaction(&tx); err != nil {
		return nil, fmt.Errorf("failed to analyze transaction: %v", err)
	}

	// Create new message with analyzed transaction
	newMsg := service.NewMessage(nil)
	if err := newMsg.SetJSON(tx); err != nil {
		return nil, fmt.Errorf("failed to serialize transaction: %v", err)
	}

	return service.MessageBatch{newMsg}, nil
}

// analyzeTransaction determines the type and description of a transaction
func (p *transactionProcessor) analyzeTransaction(tx *Transaction) error {
	// Default to unknown
	tx.Type = Unknown
	tx.Description = "Unknown transaction"

	// Check if it's a simple transfer
	if tx.Data == "0x" || tx.Data == "" {
		tx.Type = Transfer
		tx.Description = fmt.Sprintf("Transfer of %s from %s to %s", tx.Value, tx.From, tx.To)
		return nil
	}

	// Check for token approvals (ERC20/ERC721)
	if len(tx.Data) >= 10 {
		methodID := tx.Data[:10]
		switch methodID {
		case "0x095ea7b3": // ERC20 approve
			tx.Type = Approval
			tx.Description = fmt.Sprintf("Token approval from %s to %s", tx.From, tx.To)
		case "0xa22cb465": // ERC721 setApprovalForAll
			tx.Type = Approval
			tx.Description = fmt.Sprintf("NFT collection approval from %s to %s", tx.From, tx.To)
		}
	}

	// TODO: Add more transaction type analysis:
	// - Decode common DEX swap methods
	// - Identify contract deployments
	// - Parse common DeFi interactions

	return nil
}
