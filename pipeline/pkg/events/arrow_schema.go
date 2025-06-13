package events

import (
	"encoding/json"
	"time"

	"github.com/apache/arrow/go/v14/arrow"
	"github.com/apache/arrow/go/v14/arrow/array"
	"github.com/apache/arrow/go/v14/arrow/memory"
)

// EventRecord represents a flattened event record for Arrow storage
type EventRecord struct {
	// Event identification
	EventType string    `json:"event_type"`
	TxHash    string    `json:"tx_hash"`
	Timestamp time.Time `json:"timestamp"`
	
	// Entity information
	EntityType    string  `json:"entity_type"`
	EntityChain   string  `json:"entity_chain"`
	EntityAddress string  `json:"entity_address"`
	EntityName    *string `json:"entity_name,omitempty"`
	EntitySymbol  *string `json:"entity_symbol,omitempty"`
	
	// Metadata for partitioning and indexing
	Network     string `json:"network"`
	Subnet      string `json:"subnet"`
	VMType      string `json:"vm_type"`
	BlockNumber uint64 `json:"block_number"`
	BlockHash   string `json:"block_hash"`
	TxIndex     uint   `json:"tx_index"`
	
	// Time partitioning
	Year  int `json:"year"`
	Month int `json:"month"`
	Day   int `json:"day"`
	Hour  int `json:"hour"`
	
	// Flexible details as JSON
	DetailsJSON string `json:"details_json"`
}

// GetEventArrowSchema returns the Arrow schema for blockchain events
func GetEventArrowSchema() *arrow.Schema {
	return arrow.NewSchema(
		[]arrow.Field{
			// Event identification
			{Name: "event_type", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "tx_hash", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "timestamp", Type: &arrow.TimestampType{Unit: arrow.Microsecond, TimeZone: "UTC"}, Nullable: false},
			
			// Entity information
			{Name: "entity_type", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "entity_chain", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "entity_address", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "entity_name", Type: arrow.BinaryTypes.String, Nullable: true},
			{Name: "entity_symbol", Type: arrow.BinaryTypes.String, Nullable: true},
			
			// Metadata
			{Name: "network", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "subnet", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "vm_type", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "block_number", Type: arrow.PrimitiveTypes.Uint64, Nullable: false},
			{Name: "block_hash", Type: arrow.BinaryTypes.String, Nullable: false},
			{Name: "tx_index", Type: arrow.PrimitiveTypes.Uint32, Nullable: false},
			
			// Time partitioning
			{Name: "year", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "month", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "day", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			{Name: "hour", Type: arrow.PrimitiveTypes.Int32, Nullable: false},
			
			// Flexible details
			{Name: "details_json", Type: arrow.BinaryTypes.String, Nullable: false},
		},
		nil, // metadata
	)
}

// CreateEventArrowRecord converts a slice of EventRecord to Arrow Record
func CreateEventArrowRecord(records []EventRecord, mem memory.Allocator) arrow.Record {
	if len(records) == 0 {
		return nil
	}
	
	schema := GetEventArrowSchema()
	
	// Create builders for each column
	eventTypeBuilder := array.NewStringBuilder(mem)
	txHashBuilder := array.NewStringBuilder(mem)
	timestampBuilder := array.NewTimestampBuilder(mem, &arrow.TimestampType{Unit: arrow.Microsecond, TimeZone: "UTC"})
	
	entityTypeBuilder := array.NewStringBuilder(mem)
	entityChainBuilder := array.NewStringBuilder(mem)
	entityAddressBuilder := array.NewStringBuilder(mem)
	entityNameBuilder := array.NewStringBuilder(mem)
	entitySymbolBuilder := array.NewStringBuilder(mem)
	
	networkBuilder := array.NewStringBuilder(mem)
	subnetBuilder := array.NewStringBuilder(mem)
	vmTypeBuilder := array.NewStringBuilder(mem)
	blockNumberBuilder := array.NewUint64Builder(mem)
	blockHashBuilder := array.NewStringBuilder(mem)
	txIndexBuilder := array.NewUint32Builder(mem)
	
	yearBuilder := array.NewInt32Builder(mem)
	monthBuilder := array.NewInt32Builder(mem)
	dayBuilder := array.NewInt32Builder(mem)
	hourBuilder := array.NewInt32Builder(mem)
	
	detailsJSONBuilder := array.NewStringBuilder(mem)
	
	// Append data for each event
	for _, r := range records {
		eventTypeBuilder.Append(r.EventType)
		txHashBuilder.Append(r.TxHash)
		timestampBuilder.AppendTime(r.Timestamp)
		
		entityTypeBuilder.Append(r.EntityType)
		entityChainBuilder.Append(r.EntityChain)
		entityAddressBuilder.Append(r.EntityAddress)
		
		if r.EntityName != nil {
			entityNameBuilder.Append(*r.EntityName)
		} else {
			entityNameBuilder.AppendNull()
		}
		
		if r.EntitySymbol != nil {
			entitySymbolBuilder.Append(*r.EntitySymbol)
		} else {
			entitySymbolBuilder.AppendNull()
		}
		
		networkBuilder.Append(r.Network)
		subnetBuilder.Append(r.Subnet)
		vmTypeBuilder.Append(r.VMType)
		blockNumberBuilder.Append(r.BlockNumber)
		blockHashBuilder.Append(r.BlockHash)
		txIndexBuilder.Append(uint32(r.TxIndex))
		
		yearBuilder.Append(int32(r.Year))
		monthBuilder.Append(int32(r.Month))
		dayBuilder.Append(int32(r.Day))
		hourBuilder.Append(int32(r.Hour))
		
		detailsJSONBuilder.Append(r.DetailsJSON)
	}
	
	// Build arrays
	columns := []arrow.Array{
		eventTypeBuilder.NewArray(),
		txHashBuilder.NewArray(),
		timestampBuilder.NewArray(),
		entityTypeBuilder.NewArray(),
		entityChainBuilder.NewArray(),
		entityAddressBuilder.NewArray(),
		entityNameBuilder.NewArray(),
		entitySymbolBuilder.NewArray(),
		networkBuilder.NewArray(),
		subnetBuilder.NewArray(),
		vmTypeBuilder.NewArray(),
		blockNumberBuilder.NewArray(),
		blockHashBuilder.NewArray(),
		txIndexBuilder.NewArray(),
		yearBuilder.NewArray(),
		monthBuilder.NewArray(),
		dayBuilder.NewArray(),
		hourBuilder.NewArray(),
		detailsJSONBuilder.NewArray(),
	}
	
	// Create batch and record
	batch := array.NewRecord(schema, columns, int64(len(records)))
	
	// Release arrays after creating the record
	for _, col := range columns {
		defer col.Release()
	}
	
	return batch
}

// FromBlockchainEvent converts a BlockchainEvent to an EventRecord
func FromBlockchainEvent(event BlockchainEvent) (EventRecord, error) {
	// Serialize details to JSON
	detailsJSON, err := json.Marshal(event.Details)
	if err != nil {
		return EventRecord{}, err
	}
	
	record := EventRecord{
		EventType: string(event.EventType),
		TxHash:    event.TxHash,
		Timestamp: event.Timestamp,
		
		EntityType:    string(event.Entity.Type),
		EntityChain:   event.Entity.Chain,
		EntityAddress: event.Entity.Address,
		EntityName:    event.Entity.Name,
		EntitySymbol:  event.Entity.Symbol,
		
		Network:     event.Metadata.Network,
		Subnet:      event.Metadata.Subnet,
		VMType:      event.Metadata.VMType,
		BlockNumber: event.Metadata.BlockNumber,
		BlockHash:   event.Metadata.BlockHash,
		TxIndex:     event.Metadata.TxIndex,
		
		Year:  event.Metadata.Year,
		Month: event.Metadata.Month,
		Day:   event.Metadata.Day,
		Hour:  event.Metadata.Hour,
		
		DetailsJSON: string(detailsJSON),
	}
	
	return record, nil
}

// ToBlockchainEvent converts an EventRecord back to a BlockchainEvent
func (r EventRecord) ToBlockchainEvent() (BlockchainEvent, error) {
	// Deserialize details from JSON
	var details interface{}
	if err := json.Unmarshal([]byte(r.DetailsJSON), &details); err != nil {
		return BlockchainEvent{}, err
	}
	
	event := BlockchainEvent{
		EventType: EventType(r.EventType),
		Entity: Entity{
			Type:    EntityType(r.EntityType),
			Chain:   r.EntityChain,
			Address: r.EntityAddress,
			Name:    r.EntityName,
			Symbol:  r.EntitySymbol,
		},
		Timestamp: r.Timestamp,
		TxHash:    r.TxHash,
		Details:   details,
		Metadata: EventMetadata{
			Network:     r.Network,
			Subnet:      r.Subnet,
			VMType:      r.VMType,
			BlockNumber: r.BlockNumber,
			BlockHash:   r.BlockHash,
			TxIndex:     r.TxIndex,
			Year:        r.Year,
			Month:       r.Month,
			Day:         r.Day,
			Hour:        r.Hour,
		},
	}
	
	return event, nil
}
