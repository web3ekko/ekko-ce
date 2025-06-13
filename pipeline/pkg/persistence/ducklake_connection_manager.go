package persistence

import (
	"database/sql"
	"fmt"
	"log"
	"sync"
	"time"

	_ "github.com/marcboeker/go-duckdb" // DuckDB driver
)

// ConnectionManager manages DuckDB connections with proper concurrency handling
type ConnectionManager struct {
	databasePath string
	writerConn   *sql.DB
	readerPool   []*sql.DB
	poolSize     int
	mutex        sync.RWMutex
	initialized  bool
}

// NewConnectionManager creates a new connection manager
func NewConnectionManager(databasePath string, poolSize int) *ConnectionManager {
	return &ConnectionManager{
		databasePath: databasePath,
		poolSize:     poolSize,
		readerPool:   make([]*sql.DB, 0, poolSize),
	}
}

// Initialize sets up the connection manager
func (cm *ConnectionManager) Initialize() error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	if cm.initialized {
		return nil
	}

	// Create writer connection with WAL mode
	if err := cm.createWriterConnection(); err != nil {
		return fmt.Errorf("failed to create writer connection: %w", err)
	}

	// Create reader connection pool
	for i := 0; i < cm.poolSize; i++ {
		conn, err := cm.createReaderConnection()
		if err != nil {
			return fmt.Errorf("failed to create reader connection %d: %w", i, err)
		}
		cm.readerPool = append(cm.readerPool, conn)
	}

	cm.initialized = true
	log.Printf("ConnectionManager initialized with 1 writer and %d readers", cm.poolSize)
	return nil
}

// createWriterConnection creates a dedicated writer connection
func (cm *ConnectionManager) createWriterConnection() error {
	// Use WAL mode for better concurrency
	connectionString := fmt.Sprintf("%s?access_mode=read_write", cm.databasePath)
	
	conn, err := sql.Open("duckdb", connectionString)
	if err != nil {
		return fmt.Errorf("failed to open writer connection: %w", err)
	}

	// Configure for optimal writing
	if _, err := conn.Exec("PRAGMA journal_mode=WAL;"); err != nil {
		conn.Close()
		return fmt.Errorf("failed to enable WAL mode: %w", err)
	}

	if _, err := conn.Exec("PRAGMA synchronous=NORMAL;"); err != nil {
		conn.Close()
		return fmt.Errorf("failed to set synchronous mode: %w", err)
	}

	if _, err := conn.Exec("PRAGMA cache_size=10000;"); err != nil {
		conn.Close()
		return fmt.Errorf("failed to set cache size: %w", err)
	}

	// Set connection pool settings
	conn.SetMaxOpenConns(1)
	conn.SetMaxIdleConns(1)
	conn.SetConnMaxLifetime(time.Hour)

	cm.writerConn = conn
	return nil
}

// createReaderConnection creates a read-only connection
func (cm *ConnectionManager) createReaderConnection() (*sql.DB, error) {
	// Read-only connection
	connectionString := fmt.Sprintf("%s?access_mode=read_only", cm.databasePath)
	
	conn, err := sql.Open("duckdb", connectionString)
	if err != nil {
		return nil, fmt.Errorf("failed to open reader connection: %w", err)
	}

	// Configure for optimal reading
	if _, err := conn.Exec("PRAGMA cache_size=5000;"); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to set cache size: %w", err)
	}

	// Set connection pool settings
	conn.SetMaxOpenConns(1)
	conn.SetMaxIdleConns(1)
	conn.SetConnMaxLifetime(time.Hour)

	return conn, nil
}

// GetWriterConnection returns the dedicated writer connection
func (cm *ConnectionManager) GetWriterConnection() (*sql.DB, error) {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()

	if !cm.initialized {
		return nil, fmt.Errorf("connection manager not initialized")
	}

	if cm.writerConn == nil {
		return nil, fmt.Errorf("writer connection not available")
	}

	return cm.writerConn, nil
}

// GetReaderConnection returns a reader connection from the pool
func (cm *ConnectionManager) GetReaderConnection() (*sql.DB, error) {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	if !cm.initialized {
		return nil, fmt.Errorf("connection manager not initialized")
	}

	if len(cm.readerPool) == 0 {
		// Create a new reader connection if pool is empty
		conn, err := cm.createReaderConnection()
		if err != nil {
			return nil, fmt.Errorf("failed to create new reader connection: %w", err)
		}
		return conn, nil
	}

	// Get connection from pool
	conn := cm.readerPool[len(cm.readerPool)-1]
	cm.readerPool = cm.readerPool[:len(cm.readerPool)-1]
	
	return conn, nil
}

// ReturnReaderConnection returns a reader connection to the pool
func (cm *ConnectionManager) ReturnReaderConnection(conn *sql.DB) {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	if len(cm.readerPool) < cm.poolSize {
		cm.readerPool = append(cm.readerPool, conn)
	} else {
		// Pool is full, close the connection
		conn.Close()
	}
}

// ExecuteWrite executes a write operation using the writer connection
func (cm *ConnectionManager) ExecuteWrite(query string, args ...interface{}) error {
	writerConn, err := cm.GetWriterConnection()
	if err != nil {
		return err
	}

	_, err = writerConn.Exec(query, args...)
	return err
}

// ExecuteWriteWithTx executes a write operation within a transaction
func (cm *ConnectionManager) ExecuteWriteWithTx(fn func(*sql.Tx) error) error {
	writerConn, err := cm.GetWriterConnection()
	if err != nil {
		return err
	}

	tx, err := writerConn.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	if err := fn(tx); err != nil {
		return err
	}

	return tx.Commit()
}

// ExecuteRead executes a read operation using a reader connection
func (cm *ConnectionManager) ExecuteRead(query string, args ...interface{}) (*sql.Rows, error) {
	readerConn, err := cm.GetReaderConnection()
	if err != nil {
		return nil, err
	}
	defer cm.ReturnReaderConnection(readerConn)

	return readerConn.Query(query, args...)
}

// Close closes all connections
func (cm *ConnectionManager) Close() error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	var errors []error

	// Close writer connection
	if cm.writerConn != nil {
		if err := cm.writerConn.Close(); err != nil {
			errors = append(errors, fmt.Errorf("failed to close writer connection: %w", err))
		}
	}

	// Close reader connections
	for i, conn := range cm.readerPool {
		if err := conn.Close(); err != nil {
			errors = append(errors, fmt.Errorf("failed to close reader connection %d: %w", i, err))
		}
	}

	cm.readerPool = nil
	cm.writerConn = nil
	cm.initialized = false

	if len(errors) > 0 {
		return fmt.Errorf("errors closing connections: %v", errors)
	}

	log.Printf("ConnectionManager closed successfully")
	return nil
}

// HealthCheck verifies that connections are working
func (cm *ConnectionManager) HealthCheck() error {
	// Check writer connection
	writerConn, err := cm.GetWriterConnection()
	if err != nil {
		return fmt.Errorf("writer connection health check failed: %w", err)
	}

	if err := writerConn.Ping(); err != nil {
		return fmt.Errorf("writer connection ping failed: %w", err)
	}

	// Check reader connection
	readerConn, err := cm.GetReaderConnection()
	if err != nil {
		return fmt.Errorf("reader connection health check failed: %w", err)
	}
	defer cm.ReturnReaderConnection(readerConn)

	if err := readerConn.Ping(); err != nil {
		return fmt.Errorf("reader connection ping failed: %w", err)
	}

	return nil
}

// GetStats returns connection statistics
func (cm *ConnectionManager) GetStats() map[string]interface{} {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()

	stats := map[string]interface{}{
		"initialized":         cm.initialized,
		"reader_pool_size":    len(cm.readerPool),
		"max_reader_pool":     cm.poolSize,
		"writer_available":    cm.writerConn != nil,
		"database_path":       cm.databasePath,
	}

	if cm.writerConn != nil {
		dbStats := cm.writerConn.Stats()
		stats["writer_stats"] = map[string]interface{}{
			"open_connections": dbStats.OpenConnections,
			"in_use":          dbStats.InUse,
			"idle":            dbStats.Idle,
		}
	}

	return stats
}
