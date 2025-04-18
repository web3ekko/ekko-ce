package transaction

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/minio/minio-go/v7"
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

// Processor handles transaction analysis and storage
type Processor struct {
	minioClient *minio.Client
	bucket      string
}

// NewProcessor creates a new transaction processor
func NewProcessor(minioClient *minio.Client, bucket string) *Processor {
	return &Processor{
		minioClient: minioClient,
		bucket:      bucket,
	}
}

// analyzeTransaction determines the type and description of a transaction
func (p *Processor) analyzeTransaction(tx *Transaction) error {
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

// ProcessTransaction analyzes a transaction and stores it in MinIO
func (p *Processor) ProcessTransaction(ctx context.Context, tx *Transaction) error {
	// Analyze the transaction
	if err := p.analyzeTransaction(tx); err != nil {
		return fmt.Errorf("failed to analyze transaction: %w", err)
	}

	// Convert transaction to JSON
	txJSON, err := json.Marshal(tx)
	if err != nil {
		return fmt.Errorf("failed to marshal transaction: %w", err)
	}

	// Create object name with chain and date for easy querying
	objectName := fmt.Sprintf("%s/%s/%s.json",
		tx.Chain,
		tx.Timestamp.Format("2006/01/02"),
		tx.Hash,
	)

	// Upload to MinIO
	_, err = p.minioClient.PutObject(ctx, p.bucket, objectName, txJSON, int64(len(txJSON)),
		minio.PutObjectOptions{ContentType: "application/json"})
	if err != nil {
		return fmt.Errorf("failed to store transaction: %w", err)
	}

	return nil
}
