package storage

import (
	"fmt"
	"strings"
	"time"
)

// QueryOptimizer provides optimized queries that leverage Hive partitioning
type QueryOptimizer struct {
	storage *DuckDBStorage
}

// NewQueryOptimizer creates a new query optimizer
func NewQueryOptimizer(storage *DuckDBStorage) *QueryOptimizer {
	return &QueryOptimizer{
		storage: storage,
	}
}

// TimeRangeQuery represents a time-based query with partition optimization
type TimeRangeQuery struct {
	Network   string
	Subnet    string
	VMType    string
	StartTime time.Time
	EndTime   time.Time
	Limit     int
	Offset    int
}

// PartitionInfo represents partition information for query optimization
type PartitionInfo struct {
	VMType string
	Year   int
	Month  int
	Day    int
}

// GetPartitionsForTimeRange returns the partitions that need to be scanned for a time range
func (qo *QueryOptimizer) GetPartitionsForTimeRange(startTime, endTime time.Time, vmType string) []PartitionInfo {
	var partitions []PartitionInfo
	
	// Iterate through each day in the time range
	current := startTime.Truncate(24 * time.Hour)
	end := endTime.Truncate(24 * time.Hour).Add(24 * time.Hour)
	
	for current.Before(end) {
		partitions = append(partitions, PartitionInfo{
			VMType: vmType,
			Year:   current.Year(),
			Month:  int(current.Month()),
			Day:    current.Day(),
		})
		current = current.Add(24 * time.Hour)
	}
	
	return partitions
}

// BuildOptimizedQuery builds a query that leverages partition pruning
func (qo *QueryOptimizer) BuildOptimizedQuery(query TimeRangeQuery) string {
	bucketName := qo.storage.getBucketName(query.Network, query.Subnet)
	s3Path := fmt.Sprintf("s3://%s", bucketName)
	
	// Get partitions for the time range
	partitions := qo.GetPartitionsForTimeRange(query.StartTime, query.EndTime, query.VMType)
	
	// Build partition filter for optimal performance
	var partitionFilters []string
	for _, partition := range partitions {
		filter := fmt.Sprintf("(vm_type = '%s' AND year = %d AND month = %d AND day = %d)",
			partition.VMType, partition.Year, partition.Month, partition.Day)
		partitionFilters = append(partitionFilters, filter)
	}
	
	partitionFilter := ""
	if len(partitionFilters) > 0 {
		partitionFilter = "AND (" + strings.Join(partitionFilters, " OR ") + ")"
	}
	
	// Build optimized query
	optimizedQuery := fmt.Sprintf(`
		SELECT 
			block_time, block_hash, block_number,
			tx_hash, tx_index, from_address, to_address,
			value, gas_price, gas_limit, nonce, input_data, success,
			vm_type, year, month, day, hour
		FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
		WHERE block_time >= '%s' 
		AND block_time < '%s'
		%s
		ORDER BY block_time DESC, tx_index ASC
		LIMIT %d OFFSET %d
	`, s3Path, 
		query.StartTime.Format(time.RFC3339), 
		query.EndTime.Format(time.RFC3339),
		partitionFilter,
		query.Limit, 
		query.Offset)
	
	return optimizedQuery
}

// GetTransactionsByTimeRange executes an optimized time-range query
func (qo *QueryOptimizer) GetTransactionsByTimeRange(query TimeRangeQuery) ([]Transaction, error) {
	optimizedQuery := qo.BuildOptimizedQuery(query)
	
	rows, err := qo.storage.db.Query(optimizedQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to execute optimized query: %w", err)
	}
	defer rows.Close()
	
	var transactions []Transaction
	for rows.Next() {
		var tx Transaction
		err := rows.Scan(
			&tx.BlockTime, &tx.BlockHash, &tx.BlockNumber,
			&tx.TxHash, &tx.TxIndex, &tx.FromAddress, &tx.ToAddress,
			&tx.Value, &tx.GasPrice, &tx.GasLimit, &tx.Nonce, &tx.InputData, &tx.Success,
			&tx.VMType, &tx.Year, &tx.Month, &tx.Day, &tx.Hour,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan transaction: %w", err)
		}
		
		// Set network and subnet from query
		tx.Network = query.Network
		tx.Subnet = query.Subnet
		
		transactions = append(transactions, tx)
	}
	
	return transactions, nil
}

// GetTransactionCountByPartition returns transaction counts grouped by partition
func (qo *QueryOptimizer) GetTransactionCountByPartition(network, subnet string, startTime, endTime time.Time) (map[string]int64, error) {
	bucketName := qo.storage.getBucketName(network, subnet)
	s3Path := fmt.Sprintf("s3://%s", bucketName)
	
	query := fmt.Sprintf(`
		SELECT 
			vm_type,
			year,
			month,
			day,
			COUNT(*) as transaction_count
		FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
		WHERE block_time >= '%s' 
		AND block_time < '%s'
		GROUP BY vm_type, year, month, day
		ORDER BY year DESC, month DESC, day DESC, vm_type
	`, s3Path, startTime.Format(time.RFC3339), endTime.Format(time.RFC3339))
	
	rows, err := qo.storage.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to execute partition count query: %w", err)
	}
	defer rows.Close()
	
	counts := make(map[string]int64)
	for rows.Next() {
		var vmType string
		var year, month, day int
		var count int64
		
		err := rows.Scan(&vmType, &year, &month, &day, &count)
		if err != nil {
			return nil, fmt.Errorf("failed to scan partition count: %w", err)
		}
		
		partitionKey := fmt.Sprintf("%s/%d/%02d/%02d", vmType, year, month, day)
		counts[partitionKey] = count
	}
	
	return counts, nil
}

// GetHourlyTransactionVolume returns transaction volume by hour with partition optimization
func (qo *QueryOptimizer) GetHourlyTransactionVolume(network, subnet, vmType string, startTime, endTime time.Time) ([]HourlyVolume, error) {
	bucketName := qo.storage.getBucketName(network, subnet)
	s3Path := fmt.Sprintf("s3://%s", bucketName)
	
	// Get partitions for optimization
	partitions := qo.GetPartitionsForTimeRange(startTime, endTime, vmType)
	
	var partitionFilters []string
	for _, partition := range partitions {
		filter := fmt.Sprintf("(vm_type = '%s' AND year = %d AND month = %d AND day = %d)",
			partition.VMType, partition.Year, partition.Month, partition.Day)
		partitionFilters = append(partitionFilters, filter)
	}
	
	partitionFilter := ""
	if len(partitionFilters) > 0 {
		partitionFilter = "AND (" + strings.Join(partitionFilters, " OR ") + ")"
	}
	
	query := fmt.Sprintf(`
		SELECT 
			year,
			month,
			day,
			hour,
			COUNT(*) as transaction_count,
			SUM(CASE WHEN value IS NOT NULL THEN CAST(value AS BIGINT) ELSE 0 END) as total_value,
			AVG(CASE WHEN gas_price IS NOT NULL THEN CAST(gas_price AS BIGINT) ELSE 0 END) as avg_gas_price
		FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
		WHERE block_time >= '%s' 
		AND block_time < '%s'
		%s
		GROUP BY year, month, day, hour
		ORDER BY year DESC, month DESC, day DESC, hour DESC
	`, s3Path, startTime.Format(time.RFC3339), endTime.Format(time.RFC3339), partitionFilter)
	
	rows, err := qo.storage.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to execute hourly volume query: %w", err)
	}
	defer rows.Close()
	
	var volumes []HourlyVolume
	for rows.Next() {
		var volume HourlyVolume
		err := rows.Scan(
			&volume.Year, &volume.Month, &volume.Day, &volume.Hour,
			&volume.TransactionCount, &volume.TotalValue, &volume.AvgGasPrice,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan hourly volume: %w", err)
		}
		
		// Create timestamp from components
		volume.Timestamp = time.Date(volume.Year, time.Month(volume.Month), volume.Day, volume.Hour, 0, 0, 0, time.UTC)
		
		volumes = append(volumes, volume)
	}
	
	return volumes, nil
}

// GetTopAddressesByVolume returns top addresses by transaction volume with partition optimization
func (qo *QueryOptimizer) GetTopAddressesByVolume(network, subnet, vmType string, startTime, endTime time.Time, limit int) ([]AddressVolume, error) {
	bucketName := qo.storage.getBucketName(network, subnet)
	s3Path := fmt.Sprintf("s3://%s", bucketName)
	
	// Get partitions for optimization
	partitions := qo.GetPartitionsForTimeRange(startTime, endTime, vmType)
	
	var partitionFilters []string
	for _, partition := range partitions {
		filter := fmt.Sprintf("(vm_type = '%s' AND year = %d AND month = %d AND day = %d)",
			partition.VMType, partition.Year, partition.Month, partition.Day)
		partitionFilters = append(partitionFilters, filter)
	}
	
	partitionFilter := ""
	if len(partitionFilters) > 0 {
		partitionFilter = "AND (" + strings.Join(partitionFilters, " OR ") + ")"
	}
	
	query := fmt.Sprintf(`
		WITH address_stats AS (
			SELECT 
				from_address as address,
				COUNT(*) as sent_count,
				SUM(CASE WHEN value IS NOT NULL THEN CAST(value AS BIGINT) ELSE 0 END) as sent_value
			FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
			WHERE block_time >= '%s' 
			AND block_time < '%s'
			%s
			GROUP BY from_address
			
			UNION ALL
			
			SELECT 
				to_address as address,
				COUNT(*) as received_count,
				SUM(CASE WHEN value IS NOT NULL THEN CAST(value AS BIGINT) ELSE 0 END) as received_value
			FROM read_parquet('%s/**/*.parquet', hive_partitioning=true)
			WHERE block_time >= '%s' 
			AND block_time < '%s'
			AND to_address IS NOT NULL
			%s
			GROUP BY to_address
		)
		SELECT 
			address,
			SUM(sent_count) as total_sent,
			SUM(received_count) as total_received,
			SUM(sent_value) as total_sent_value,
			SUM(received_value) as total_received_value,
			SUM(sent_count + received_count) as total_transactions,
			SUM(sent_value + received_value) as total_volume
		FROM address_stats
		GROUP BY address
		ORDER BY total_volume DESC
		LIMIT %d
	`, s3Path, startTime.Format(time.RFC3339), endTime.Format(time.RFC3339), partitionFilter,
		s3Path, startTime.Format(time.RFC3339), endTime.Format(time.RFC3339), partitionFilter,
		limit)
	
	rows, err := qo.storage.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to execute top addresses query: %w", err)
	}
	defer rows.Close()
	
	var addresses []AddressVolume
	for rows.Next() {
		var addr AddressVolume
		err := rows.Scan(
			&addr.Address, &addr.TotalSent, &addr.TotalReceived,
			&addr.TotalSentValue, &addr.TotalReceivedValue,
			&addr.TotalTransactions, &addr.TotalVolume,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan address volume: %w", err)
		}
		
		addresses = append(addresses, addr)
	}
	
	return addresses, nil
}

// HourlyVolume represents transaction volume data for an hour
type HourlyVolume struct {
	Timestamp        time.Time `json:"timestamp"`
	Year             int       `json:"year"`
	Month            int       `json:"month"`
	Day              int       `json:"day"`
	Hour             int       `json:"hour"`
	TransactionCount int64     `json:"transaction_count"`
	TotalValue       int64     `json:"total_value"`
	AvgGasPrice      float64   `json:"avg_gas_price"`
}

// AddressVolume represents transaction volume data for an address
type AddressVolume struct {
	Address              string `json:"address"`
	TotalSent            int64  `json:"total_sent"`
	TotalReceived        int64  `json:"total_received"`
	TotalSentValue       int64  `json:"total_sent_value"`
	TotalReceivedValue   int64  `json:"total_received_value"`
	TotalTransactions    int64  `json:"total_transactions"`
	TotalVolume          int64  `json:"total_volume"`
}
