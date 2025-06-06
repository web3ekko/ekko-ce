package persistence

import (
	"strconv"
	"time"

	"github.com/apache/arrow/go/v15/arrow"
	"github.com/apache/arrow/go/v15/arrow/array"
	"github.com/apache/arrow/go/v15/arrow/memory"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
)

// TransactionRecord defines the structure for transactions stored in Arrow format
type TransactionRecord struct {
	// Partition columns (for faster filtering)
	Network       string
	Subnet        string
	VMType        string
	
	// Time fields (optimized for range queries)
	BlockTime     time.Time
	Year          int
	Month         int
	Day           int
	Hour          int
	
	// Block information
	BlockHash     string
	BlockNumber   uint64
	
	// Transaction data
	TxHash        string
	TxIndex       uint
	From          string
	To            string
	Value         string
	GasPrice      string
	GasLimit      string
	Nonce         string
	InputData     []byte
	
	// Derived fields
	Success       bool
}

// GetArrowSchema returns the Arrow schema for transaction records
func GetArrowSchema() *arrow.Schema {
	return arrow.NewSchema(
		[]arrow.Field{
			{Name: "network", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "subnet", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "vm_type", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "block_time", Type: &arrow.TimestampType{Unit: arrow.Microsecond, TimeZone: "UTC"}, Nullable: false},
			{Name: "year", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "month", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "day", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "hour", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "block_hash", Type: arrow.BinaryTypes.String, Nullable: true},
			{Name: "block_number", Type: arrow.PrimitiveTypes.Uint64, Nullable: true},
			{Name: "tx_hash", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "tx_index", Type: arrow.PrimitiveTypes.Uint32, Nullable: true},
			{Name: "from", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "to", Type: arrow.BinaryTypes.String, Nullable: true},
			{Name: "value", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "gas_price", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "gas_limit", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "nonce", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "input_data", Type: arrow.BinaryTypes.Binary, Nullable: true},
			{Name: "success", Type: arrow.FixedWidthTypes.Boolean, Nullable: false},
		},
		nil, // metadata
	)
}

// CreateArrowRecord converts a slice of TransactionRecord to Arrow Record
func CreateArrowRecord(records []TransactionRecord, mem memory.Allocator) arrow.Record {
	if len(records) == 0 {
		return nil
	}
	
	schema := GetArrowSchema()
	
	// Create builders for each column
	networkBuilder := array.NewStringBuilder(mem)
	subnetBuilder := array.NewStringBuilder(mem)
	vmTypeBuilder := array.NewStringBuilder(mem)
	blockTimeBuilder := array.NewTimestampBuilder(mem, &arrow.TimestampType{Unit: arrow.Microsecond, TimeZone: "UTC"})
	yearBuilder := array.NewInt32Builder(mem)
	monthBuilder := array.NewInt32Builder(mem)
	dayBuilder := array.NewInt32Builder(mem)
	hourBuilder := array.NewInt32Builder(mem)
	blockHashBuilder := array.NewStringBuilder(mem)
	blockNumberBuilder := array.NewUint64Builder(mem)
	txHashBuilder := array.NewStringBuilder(mem)
	txIndexBuilder := array.NewUint32Builder(mem)
	fromBuilder := array.NewStringBuilder(mem)
	toBuilder := array.NewStringBuilder(mem)
	valueBuilder := array.NewStringBuilder(mem)
	gasPriceBuilder := array.NewStringBuilder(mem)
	gasLimitBuilder := array.NewStringBuilder(mem)
	nonceBuilder := array.NewStringBuilder(mem)
	inputDataBuilder := array.NewBinaryBuilder(mem, arrow.BinaryTypes.Binary)
	successBuilder := array.NewBooleanBuilder(mem)
	
	// Defer release of all builders
	defer networkBuilder.Release()
	defer subnetBuilder.Release()
	defer vmTypeBuilder.Release()
	defer blockTimeBuilder.Release()
	defer yearBuilder.Release()
	defer monthBuilder.Release()
	defer dayBuilder.Release()
	defer hourBuilder.Release()
	defer blockHashBuilder.Release()
	defer blockNumberBuilder.Release()
	defer txHashBuilder.Release()
	defer txIndexBuilder.Release()
	defer fromBuilder.Release()
	defer toBuilder.Release()
	defer valueBuilder.Release()
	defer gasPriceBuilder.Release()
	defer gasLimitBuilder.Release()
	defer nonceBuilder.Release()
	defer inputDataBuilder.Release()
	defer successBuilder.Release()
	
	// Append data for each transaction
	for _, r := range records {
		networkBuilder.Append(r.Network)
		subnetBuilder.Append(r.Subnet)
		vmTypeBuilder.Append(r.VMType)
		blockTimeBuilder.AppendTime(r.BlockTime)
		yearBuilder.Append(int32(r.Year))
		monthBuilder.Append(int32(r.Month))
		dayBuilder.Append(int32(r.Day))
		hourBuilder.Append(int32(r.Hour))
		blockHashBuilder.Append(r.BlockHash)
		blockNumberBuilder.Append(r.BlockNumber)
		txHashBuilder.Append(r.TxHash)
		txIndexBuilder.Append(uint32(r.TxIndex))
		fromBuilder.Append(r.From)
		toBuilder.Append(r.To)
		valueBuilder.Append(r.Value)
		gasPriceBuilder.Append(r.GasPrice)
		gasLimitBuilder.Append(r.GasLimit)
		nonceBuilder.Append(r.Nonce)
		inputDataBuilder.Append(r.InputData)
		successBuilder.Append(r.Success)
	}
	
	// Build the column arrays
	columns := []arrow.Array{
		networkBuilder.NewArray(),
		subnetBuilder.NewArray(),
		vmTypeBuilder.NewArray(),
		blockTimeBuilder.NewArray(),
		yearBuilder.NewArray(),
		monthBuilder.NewArray(),
		dayBuilder.NewArray(),
		hourBuilder.NewArray(),
		blockHashBuilder.NewArray(),
		blockNumberBuilder.NewArray(),
		txHashBuilder.NewArray(),
		txIndexBuilder.NewArray(),
		fromBuilder.NewArray(),
		toBuilder.NewArray(),
		valueBuilder.NewArray(),
		gasPriceBuilder.NewArray(),
		gasLimitBuilder.NewArray(),
		nonceBuilder.NewArray(),
		inputDataBuilder.NewArray(),
		successBuilder.NewArray(),
	}
	
	// Create batch and record
	batch := array.NewRecord(schema, columns, int64(len(records)))
	
	// Release arrays after creating the record
	for _, col := range columns {
		defer col.Release()
	}
	
	return batch
}

// FromBlockchainTransaction converts a blockchain.Transaction to a TransactionRecord
func FromBlockchainTransaction(tx blockchain.Transaction, network, subnet, vmType string, blockTime time.Time) TransactionRecord {
	record := TransactionRecord{
		Network:     network,
		Subnet:      subnet,
		VMType:      vmType,
		BlockTime:   blockTime,
		Year:        blockTime.Year(),
		Month:       int(blockTime.Month()),
		Day:         blockTime.Day(),
		Hour:        blockTime.Hour(),
		TxHash:      tx.Hash,
		From:        tx.From,
		Value:       tx.Value,
		GasPrice:    tx.GasPrice,
		GasLimit:    tx.Gas,
		Nonce:       tx.Nonce,
		InputData:   []byte(tx.Data),
		Success:     true, // Default to true, we'll set based on receipt data if available
	}

	// Handle nil pointer for To address
	if tx.To != nil {
		record.To = *tx.To
	}

	// Handle nil pointer for BlockHash
	if tx.BlockHash != nil {
		record.BlockHash = *tx.BlockHash
	}

	// Handle nil pointer for BlockNumber
	if tx.BlockNumber != nil {
		blockNum, err := strconv.ParseUint(*tx.BlockNumber, 0, 64)
		if err == nil {
			record.BlockNumber = blockNum
		}
	}

	// Handle nil pointer for TransactionIndex
	if tx.TransactionIndex != nil {
		txIndex, err := strconv.ParseUint(*tx.TransactionIndex, 0, 32)
		if err == nil {
			record.TxIndex = uint(txIndex)
		}
	}

	return record
}

// BatchMetadata contains information about a batch of transactions
type BatchMetadata struct {
	Network       string    `json:"network"`
	Subnet        string    `json:"subnet"`
	VMType        string    `json:"vm_type"`
	StartBlock    uint64    `json:"start_block"`
	EndBlock      uint64    `json:"end_block"`
	StartTime     time.Time `json:"start_time"`
	EndTime       time.Time `json:"end_time"`
	TxCount       int       `json:"tx_count"`
	FilePath      string    `json:"file_path"`
	FileSize      int64     `json:"file_size"`
	CreatedAt     time.Time `json:"created_at"`
}
