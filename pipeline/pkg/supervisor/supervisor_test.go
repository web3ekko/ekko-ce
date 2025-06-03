package supervisor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"reflect"
	"strings" // Added strings import
	"sync"
	"testing"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	tcnats "github.com/testcontainers/testcontainers-go/modules/nats" // Alias for nats module
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

// mockKeyLister implements nats.KeyLister for testing
type mockKeyLister struct {
	keys []string
	err  error
}

func (mkl *mockKeyLister) Keys() <-chan string {
	ch := make(chan string, len(mkl.keys))
	go func() {
		for _, k := range mkl.keys {
			ch <- k
		}
		close(ch)
	}()
	return ch
}

func (mkl *mockKeyLister) Err() error {
	return mkl.err
}

func (mkl *mockKeyLister) Stop() error {
	// For mock, this can be a no-op or manage internal state if needed.
	return nil
}

// mockKeyValueEntry implements nats.KeyValueEntry for testing
type mockKeyValueEntry struct {
	bucket    string
	key       string
	value     []byte
	revision  uint64
	created   time.Time
	delta     uint64
	operation nats.KeyValueOp
}

func (m *mockKeyValueEntry) Bucket() string        { return m.bucket }
func (m *mockKeyValueEntry) Key() string           { return m.key }
func (m *mockKeyValueEntry) Value() []byte         { return m.value }
func (m *mockKeyValueEntry) Revision() uint64      { return m.revision }
func (m *mockKeyValueEntry) Created() time.Time    { return m.created }
func (m *mockKeyValueEntry) Delta() uint64         { return m.delta }
func (m *mockKeyValueEntry) Operation() nats.KeyValueOp { return m.operation }

// mockKeyValueStore implements nats.KeyValue for testing
type mockKeyValueStore struct {
	mu      sync.Mutex
	data    map[string][]byte
	bucketName string
}

func newMockKeyValueStore(bucketName string) *mockKeyValueStore {
	return &mockKeyValueStore{
		data:    make(map[string][]byte),
		bucketName: bucketName,
	}
}

func (m *mockKeyValueStore) Bucket() string { return m.bucketName }

func (m *mockKeyValueStore) Get(key string) (nats.KeyValueEntry, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	val, ok := m.data[key]
	if !ok {
		return nil, nats.ErrKeyNotFound
	}
	return &mockKeyValueEntry{
		bucket: m.bucketName,
		key:    key,
		value:  val,
		// Populate other fields as needed for specific tests
	}, nil
}

func (m *mockKeyValueStore) Put(key string, value []byte) (uint64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = value
	return 1, nil // Simplified revision handling
}

func (m *mockKeyValueStore) Create(key string, value []byte) (uint64, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, exists := m.data[key]; exists {
		return 0, nats.ErrKeyExists
	}
	m.data[key] = value
	return 1, nil
}

func (m *mockKeyValueStore) Delete(key string, opts ...nats.DeleteOpt) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.data[key]; !ok {
		return nats.ErrKeyNotFound // Or some other appropriate error if key must exist
	}
	delete(m.data, key)
	return nil
}

func (m *mockKeyValueStore) Keys(opts ...nats.WatchOpt) ([]string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	keys := make([]string, 0, len(m.data))
	for k := range m.data {
		keys = append(keys, k)
	}
	return keys, nil
}

// Implement other nats.KeyValue methods as needed, returning nil or errors for now.
func (m *mockKeyValueStore) Update(key string, value []byte, last uint64) (uint64, error) {
	return 0, fmt.Errorf("Update not implemented in mock")
}
func (m *mockKeyValueStore) Watch(keys string, opts ...nats.WatchOpt) (nats.KeyWatcher, error) {
	return nil, fmt.Errorf("Watch not implemented in mock")
}
func (m *mockKeyValueStore) WatchAll(opts ...nats.WatchOpt) (nats.KeyWatcher, error) {
	return nil, fmt.Errorf("WatchAll not implemented in mock")
}
func (m *mockKeyValueStore) History(key string, opts ...nats.WatchOpt) ([]nats.KeyValueEntry, error) {
	return nil, fmt.Errorf("History not implemented in mock")
}
func (m *mockKeyValueStore) Status() (nats.KeyValueStatus, error) {
	return nil, fmt.Errorf("Status not implemented in mock")
}
func (m *mockKeyValueStore) PurgeDeletes(opts ...nats.PurgeOpt) error {
	return fmt.Errorf("PurgeDeletes not implemented in mock")
}
func (m *mockKeyValueStore) Purge(key string, opts ...nats.DeleteOpt) error {
	return fmt.Errorf("Purge not implemented in mock")
}

func (m *mockKeyValueStore) ListKeys(opts ...nats.WatchOpt) (nats.KeyLister, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	keys := make([]string, 0, len(m.data))
	for k := range m.data {
		// Apply watch options filtering if necessary (e.g., prefix)
		// For now, returning all keys
		keys = append(keys, k)
	}
	return &mockKeyLister{keys: keys, err: nil}, nil
}

func (m *mockKeyValueStore) PutString(key string, value string) (revision uint64, err error) {
	// Simplified PutString for mock
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data[key] = []byte(value)
	// Increment a global revision or handle revision per key if needed for complex tests
	// For now, returning a static revision
	return 1, nil
}

// mockNatsConn implements the relevant parts of nats.Conn for testing.
type mockNatsConn struct {
	nats.Conn // Embed nats.Conn to avoid implementing all methods
	// Add fields here if you need to track calls to specific nats.Conn methods
	publishCalls map[string][][]byte // subject -> list of data []byte
	mu           sync.Mutex
}

func newMockNatsConn() *mockNatsConn {
	// Initialize the embedded nats.Conn. Operations on this conn will likely panic
	// if not mocked or if it's not connected, which is acceptable if the test path
	// doesn't hit those specific unmocked operations on the conn itself.
	return &mockNatsConn{
		Conn:         nats.Conn{}, 
		publishCalls: make(map[string][][]byte),
	}
}

// Publish is a mock implementation.
func (m *mockNatsConn) Publish(subj string, data []byte) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.publishCalls == nil {
		m.publishCalls = make(map[string][][]byte)
	}
	m.publishCalls[subj] = append(m.publishCalls[subj], data)
	return nil // Simulate successful publish
}

// JetStream is a mock implementation if supervisor interacts with JetStream directly.
func (m *mockNatsConn) JetStream(opts ...nats.JSOpt) (nats.JetStreamContext, error) {
	// Return a mock JetStreamContext if needed, or an error if it's not expected to be called.
	// For now, let's assume it might be called for KV store, so return a basic mock.
	return &mockJetStreamContext{}, nil
}

// mockJetStreamContext implements nats.JetStreamContext for testing.
type mockJetStreamContext struct {
	nats.JetStreamContext
}

// KeyValue is a mock implementation.
func (mjs *mockJetStreamContext) KeyValue(bucket string) (nats.KeyValue, error) {
	// This is tricky. If the supervisor gets the KV store via nc.JetStream().KeyValue(),
	// then this mock needs to return the mockKeyValueStore.
	// However, our supervisor currently takes nats.KeyValue directly.
	// So, this might not be strictly needed unless other parts of nats.Conn are used.
	// For now, return a new mock KV store or an error.
	// Let's return an error to see if this path is even hit.
	return nil, fmt.Errorf("mockJetStreamContext.KeyValue not expected to be called directly in this test setup")
}

func (m *mockKeyValueStore) GetRevision(key string, rev uint64) (nats.KeyValueEntry, error) {
	// For mock, we might not need full revision logic. Return based on current data or specific test needs.
	m.mu.Lock()
	defer m.mu.Unlock()

	val, ok := m.data[key]
	if !ok {
		return nil, nats.ErrKeyNotFound
	}
	// This mock doesn't store historical revisions, so we return the current value
	// if the requested revision is 0 (latest) or matches a simplified current revision (e.g., 1).
	// A real GetRevision would look up a specific version.
	if rev == 0 || rev == 1 { // Simplified logic for mock
		return &mockKeyValueEntry{
			bucket: m.bucketName,
			key:    key,
			value:  val,
			revision: 1, // Assuming current revision is 1 for simplicity
		}, nil
	}
	return nil, nats.ErrKeyNotFound // Or a specific error for revision not found
}

// mockManagedPipeline implements the ManagedPipeline's relevant methods for testing the supervisor.
type mockManagedPipeline struct {
	mu                     sync.Mutex
	id                     string
	nodes                  []common.NodeConfig
	updateCalled           bool
	updateNodeConfigsCalls [][]common.NodeConfig
	runCalled              bool
	stopCalled             bool
	runErr                 error
	updateNodeConfigsErr   error // Error to return from UpdateNodeConfigs if set

	// Per-instance lifecycle management
	wg             *sync.WaitGroup    // To wait for the Run goroutine to complete
	instanceCtx    context.Context    // Context for this specific pipeline instance's Run goroutine
	instanceCancel context.CancelFunc // CancelFunc for instanceCtx
}

func newMockManagedPipeline(id string, initialNodes []common.NodeConfig) *mockManagedPipeline {
	pipelineCtx, pipelineCancel := context.WithCancel(context.Background())
	return &mockManagedPipeline{
		id:                     id,
		nodes:                  initialNodes,
		updateNodeConfigsCalls: make([][]common.NodeConfig, 0),
		wg:                     new(sync.WaitGroup),
		instanceCtx:            pipelineCtx,
		instanceCancel:         pipelineCancel,
	}
}

func (m *mockManagedPipeline) Run() error {
	m.mu.Lock()
	if m.runCalled { // Prevent double run, though supervisor logic should also prevent this
		m.mu.Unlock()
		return fmt.Errorf("pipeline %s already running", m.id)
	}
	m.runCalled = true
	m.stopCalled = false // Reset stopCalled if it's being reused (though new instances are typical)
	m.wg.Add(1)
	m.mu.Unlock()

	go func() {
		defer m.wg.Done()
		log.Printf("MockPipeline %s: Run goroutine started.", m.id)
		select {
		case <-m.instanceCtx.Done():
			log.Printf("MockPipeline %s: instanceCtx cancelled. Run goroutine exiting.", m.id)
			return
		}
	}()

	return m.runErr // runErr is for synchronous errors during Run startup
}

func (m *mockManagedPipeline) Stop() {
	m.mu.Lock()
	if m.stopCalled {
		m.mu.Unlock()
		log.Printf("MockPipeline %s: Stop() called but already stopped.", m.id)
		return
	}
	m.stopCalled = true
	log.Printf("MockPipeline %s: Stop called, setting stopCalled = true.", m.id)
	m.mu.Unlock()

	if m.instanceCancel != nil {
		log.Printf("MockPipeline %s: Calling instanceCancel().", m.id)
		m.instanceCancel() // Signal the Run goroutine to terminate
	} else {
		log.Printf("MockPipeline %s: instanceCancel is nil, cannot cancel context.", m.id)
	}
}

func (m *mockManagedPipeline) Wait() {
	log.Printf("MockPipeline %s: Wait() called, calling wg.Wait().", m.id)
	m.wg.Wait() // Wait for the Run goroutine to complete
	log.Printf("MockPipeline %s: wg.Wait() completed in Wait().", m.id)
}



func (m *mockManagedPipeline) UpdateNodeConfigs(configs []common.NodeConfig) error {
	log.Printf("MockPipeline instance %p (id: %s): ENTERING UpdateNodeConfigs with %d nodes. Current updateCalled: %v", m, m.id, len(configs), m.updateCalled)
	m.mu.Lock()
	defer m.mu.Unlock()
	m.nodes = append([]common.NodeConfig{}, configs...) // Keep nodes field updated
	m.updateCalled = true
	m.updateNodeConfigsCalls = append(m.updateNodeConfigsCalls, append([]common.NodeConfig{}, configs...))
	log.Printf("MockPipeline instance %p (id: %s): UpdateNodeConfigs FINISHED. New updateCalled: %v. Total calls: %d", m, m.id, m.updateCalled, len(m.updateNodeConfigsCalls))
	return m.updateNodeConfigsErr
}

// Helper methods for tests
func (m *mockManagedPipeline) hasRun() bool {
	return m.runCalled
}

func (m *mockManagedPipeline) IsStopped() bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.stopCalled
}

func (m *mockManagedPipeline) updateCount() int {
	return len(m.updateNodeConfigsCalls)
}

func (m *mockManagedPipeline) lastUpdateConfigs() []common.NodeConfig {
	if len(m.updateNodeConfigsCalls) == 0 {
		return nil
	}
	return m.updateNodeConfigsCalls[len(m.updateNodeConfigsCalls)-1]
}


// TestSynchronizeServices_NodeCreated tests the creation of a new pipeline when a node appears.
func TestSynchronizeServices_NodeCreated(t *testing.T) {
	ctx := context.Background()

	// Setup NATS container
	natsContainer, err := tcnats.RunContainer(ctx, testcontainers.WithImage("nats:2.10-alpine"))
	require.NoError(t, err, "Failed to start NATS container")
	defer func() {
		if err := natsContainer.Terminate(ctx); err != nil {
			t.Fatalf("Failed to terminate NATS container: %s", err)
		}
	}()

	natsURL, err := natsContainer.ConnectionString(ctx)
	require.NoError(t, err, "Failed to get NATS connection string")

	nc, err := nats.Connect(natsURL)
	require.NoError(t, err, "Failed to connect to NATS container")
	defer nc.Close()

	js, err := nc.JetStream()
	require.NoError(t, err, "Failed to get JetStream context")

	kvStoreName := "node_configs"
	kv, err := js.CreateKeyValue(&nats.KeyValueConfig{Bucket: kvStoreName})
	require.NoError(t, err, "Failed to create KV store")

	// Define key prefix locally for the test, matching supervisor.go
	const kvStoreKeyPrefix = "nodestore."

	// Setup Supervisor with real NATS connection and KV store
	supervisor, err := NewPipelineSupervisor(nc, kv, nil /*redisClient*/)
	require.NoError(t, err)
	supervisor.supervisorCtx = context.Background() // Initialize supervisorCtx for the test to prevent panic in NewFetcherSupervisor

	// Store the original factory function
	originalNewManagedPipeline := newManagedPipelineFunc
	defer func() { newManagedPipelineFunc = originalNewManagedPipeline }() // Restore original

	var createdMockPipeline *mockManagedPipeline

	// Override the factory function to return our mock
	newManagedPipelineFunc = func(parentCtx context.Context, network string, subnet string, vmType string, initialNodes []common.NodeConfig, natsConn *nats.Conn, redisClient decoder.RedisClient, statusUpdater NodeStatusUpdater) (ManagedPipelineInterface, error) {
		// The mockManagedPipeline doesn't use all these params directly, but we need to match the signature.
		// The 'id' for mockManagedPipeline can be generated or taken from network/subnet/vmType if needed for the mock's internal state.
		mockID := fmt.Sprintf("%s-%s-%s", network, subnet, vmType)
		mp := newMockManagedPipeline(mockID, initialNodes)
		createdMockPipeline = mp
		return mp, nil // Return the mock and a nil error
	}

	// Initial Node Configuration
	nodeCfg := common.NodeConfig{
		ID:          "node1", // Updated to use ID, IsEnabled, HttpURL
		Network:     "testnet",
		Subnet:      "testsub",
		VMType:      "evm",
		IsEnabled:   true,
		Name:        "Test Node 1",
		Description: "A test node",
		HttpURL:     "http://localhost:8545",
	}
	key := kvStoreKeyPrefix + nodeCfg.ID
	data, _ := json.Marshal(nodeCfg)
	_, err = kv.Put(key, data) // Use the real KV store
	require.NoError(t, err)

	// Action
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err)

	// Assertions
	assert.NotNil(t, createdMockPipeline, "A new pipeline should have been created")
	assert.Eventually(t, func() bool {
		createdMockPipeline.mu.Lock()
		defer createdMockPipeline.mu.Unlock()
		return createdMockPipeline.runCalled
	}, time.Second*1, time.Millisecond*10, "The new pipeline's Run method should have been called within the timeout period")
	assert.False(t, createdMockPipeline.IsStopped(), "The new pipeline's Stop method should not have been called")
	assert.Equal(t, 1, createdMockPipeline.updateCount(), "UpdateNodeConfigs should have been called once for a new pipeline")

	// Check if the pipeline is in runningServices
	supervisor.servicesMutex.Lock()
	pipelineID := generatePipelineID(nodeCfg)
	_, exists := supervisor.runningServices[pipelineID]
	supervisor.servicesMutex.Unlock()
	assert.True(t, exists, "Pipeline should be in runningServices map")
}

func TestSynchronizeServices_NodeUpdated(t *testing.T) {
	ctx := context.Background()

	// Setup NATS container
	natsContainer, err := tcnats.RunContainer(ctx, testcontainers.WithImage("nats:2.10-alpine"))
	require.NoError(t, err, "Failed to start NATS container")
	defer func() {
		if err := natsContainer.Terminate(ctx); err != nil {
			t.Fatalf("Failed to terminate NATS container: %s", err)
		}
	}()

	natsURL, err := natsContainer.ConnectionString(ctx)
	require.NoError(t, err, "Failed to get NATS connection string")

	nc, err := nats.Connect(natsURL)
	require.NoError(t, err, "Failed to connect to NATS container")
	defer nc.Close()

	js, err := nc.JetStream()
	require.NoError(t, err, "Failed to get JetStream context")

	kvStoreName := "node_configs"
	kv, err := js.CreateKeyValue(&nats.KeyValueConfig{Bucket: kvStoreName})
	require.NoError(t, err, "Failed to create KV store")

	// Define key prefix locally for the test, matching supervisor.go
	const kvStoreKeyPrefix = "nodestore."

	// Setup Supervisor with real NATS connection and KV store
	supervisor, err := NewPipelineSupervisor(nc, kv, nil /*redisClient*/)
	require.NoError(t, err, "NewPipelineSupervisor should not error")
	supervisor.supervisorCtx = context.Background() // Initialize supervisorCtx for the test

	var createdMockPipeline *mockManagedPipeline
	initialPipelinesCreated := 0

	// Override the factory function to return our mock and count creations
	originalNewManagedPipelineFunc := newManagedPipelineFunc
	newManagedPipelineFunc = func(parentCtx context.Context, network string, subnet string, vmType string, initialNodes []common.NodeConfig, natsConn *nats.Conn, redisClient decoder.RedisClient, statusUpdater NodeStatusUpdater) (ManagedPipelineInterface, error) {
		// Construct mockID similar to how NewManagedPipeline does for its internal pipelineID
		mockID := fmt.Sprintf("%s-%s-%s", strings.ToLower(network), strings.ToLower(subnet), strings.ToLower(vmType))
		mp := newMockManagedPipeline(mockID, initialNodes)
		createdMockPipeline = mp
		initialPipelinesCreated++
		// The mock doesn't use statusUpdater, so passing the supervisor instance or nil is fine.
		// For the actual NewManagedPipeline, the supervisor passes itself as statusUpdater.
		return mp, nil
	}
	defer func() { newManagedPipelineFunc = originalNewManagedPipelineFunc }() // Restore original factory

	// Initial Node Configuration
	initialNodeCfg := common.NodeConfig{
		ID:          "node-update-test-1", // Changed NodeID to ID
		Network:     "testnet-update",
		Subnet:      "testsub-update",
		VMType:      "evm-update",
		IsEnabled:   true, // Changed Enabled to IsEnabled
		Name:        "Test Node Update 1",
		Description: "Initial config for update test",
		HttpURL:     "http://localhost:9545", // Changed URLs to HttpURL (string)
	}
	key := kvStoreKeyPrefix + initialNodeCfg.ID
	initialData, _ := json.Marshal(initialNodeCfg)
	_, err = kv.Put(key, initialData) // Use real KV store
	require.NoError(t, err, "Put initial node config should not error")

	// First synchronization: Create the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (initial) should not error")

	require.NotNil(t, createdMockPipeline, "A pipeline should have been created initially")
	assert.Equal(t, 1, initialPipelinesCreated, "Exactly one pipeline should be created initially")
	assert.Eventually(t, func() bool {
		createdMockPipeline.mu.Lock()
		defer createdMockPipeline.mu.Unlock()
		return createdMockPipeline.runCalled
	}, time.Second*1, time.Millisecond*10, "Initial pipeline's Run method should have been called")
	// Ensure UpdateNodeConfigs was not called yet
	assert.Equal(t, 1, len(createdMockPipeline.updateNodeConfigsCalls), "UpdateNodeConfigs should have been called once initially")


	// Action: Update the node configuration
	updatedNodeCfg := initialNodeCfg // Copy initial config
	updatedNodeCfg.Description = "Updated Description for node-update-test-1"
	updatedNodeCfg.HttpURL = "http://localhost:9546" // Changed URLs to HttpURL, assuming single URL update for simplicity

	updatedData, _ := json.Marshal(updatedNodeCfg)
	_, err = kv.Put(key, updatedData) // Use real KV store, use the same key to update
	require.NoError(t, err, "Put updated node config should not error")

	// Reset runCalled on the mock before the update synchronization to specifically check the update action
	createdMockPipeline.mu.Lock()
	createdMockPipeline.runCalled = false 
	createdMockPipeline.mu.Unlock()

	// Second synchronization: Update the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (update) should not error")

	// Assertions for update
	assert.Equal(t, 1, initialPipelinesCreated, "No new pipeline should be created on update")

	createdMockPipeline.mu.Lock()
	defer createdMockPipeline.mu.Unlock()

	assert.False(t, createdMockPipeline.runCalled, "Run should not be called again on update")
	assert.Equal(t, 2, len(createdMockPipeline.updateNodeConfigsCalls), "UpdateNodeConfigs should be called twice in total (create + update)")
	require.Len(t, createdMockPipeline.updateNodeConfigsCalls[1], 1, "UpdateNodeConfigs (second call) should be called with one node config")
	assert.Equal(t, updatedNodeCfg, createdMockPipeline.updateNodeConfigsCalls[1][0], "UpdateNodeConfigs (second call) should be called with the updated node config")
	assert.False(t, createdMockPipeline.stopCalled, "Stop should not be called on update")
}

// TestSynchronizeServices_NodeDeleted tests that deleting a node configuration
// results in the pipeline being stopped and removed.
func TestSynchronizeServices_NodeDeleted(t *testing.T) {
	ctx := context.Background()

	// Setup NATS container
	natsContainer, err := tcnats.RunContainer(ctx, testcontainers.WithImage("nats:2.10-alpine"))
	require.NoError(t, err, "Failed to start NATS container")
	defer func() {
		if err := natsContainer.Terminate(ctx); err != nil {
			t.Fatalf("Failed to terminate NATS container: %s", err)
		}
	}()

	natsURL, err := natsContainer.ConnectionString(ctx)
	require.NoError(t, err, "Failed to get NATS connection string")

	nc, err := nats.Connect(natsURL)
	require.NoError(t, err, "Failed to connect to NATS container")
	defer nc.Close()

	js, err := nc.JetStream()
	require.NoError(t, err, "Failed to get JetStream context")

	kvStoreName := "node_configs"
	kv, err := js.CreateKeyValue(&nats.KeyValueConfig{Bucket: kvStoreName})
	require.NoError(t, err, "Failed to create KV store")

	// Define key prefix locally for the test, matching supervisor.go
	const kvStoreKeyPrefix = "nodestore."

	// Setup Supervisor with real NATS connection and KV store
	supervisor, err := NewPipelineSupervisor(nc, kv, nil /*redisClient*/)
	require.NoError(t, err, "NewPipelineSupervisor should not error")
	supervisor.supervisorCtx = context.Background() // Initialize supervisorCtx for the test

	var createdMockPipeline *mockManagedPipeline
	pipelinesCreatedCount := 0

	// Override the factory function
	originalNewManagedPipelineFunc := newManagedPipelineFunc
	newManagedPipelineFunc = func(parentCtx context.Context, network string, subnet string, vmType string, initialNodes []common.NodeConfig, natsConn *nats.Conn, redisClient decoder.RedisClient, statusUpdater NodeStatusUpdater) (ManagedPipelineInterface, error) {
		mockID := fmt.Sprintf("%s-%s-%s", strings.ToLower(network), strings.ToLower(subnet), strings.ToLower(vmType))
		mp := newMockManagedPipeline(mockID, initialNodes)
		createdMockPipeline = mp
		pipelinesCreatedCount++
		return mp, nil
	}
	defer func() { newManagedPipelineFunc = originalNewManagedPipelineFunc }()

	// Initial Node Configuration
	nodeCfg := common.NodeConfig{
		ID:          "node-delete-test-1",
		Network:     "testnet-delete",
		Subnet:      "testsub-delete",
		VMType:      "evm-delete",
		IsEnabled:   true,
		Name:        "Test Node Delete 1",
		HttpURL:     "http://localhost:10545",
	}
	key := kvStoreKeyPrefix + nodeCfg.ID
	initialData, _ := json.Marshal(nodeCfg)
	_, err = kv.Put(key, initialData)
	require.NoError(t, err, "Put initial node config should not error")

	// First synchronization: Create the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (initial) should not error")

	require.NotNil(t, createdMockPipeline, "A pipeline should have been created initially")
	assert.Equal(t, 1, pipelinesCreatedCount, "Exactly one pipeline should be created initially")
	assert.Eventually(t, func() bool {
		createdMockPipeline.mu.Lock()
		defer createdMockPipeline.mu.Unlock()
		return createdMockPipeline.runCalled
	}, time.Second*1, time.Millisecond*10, "Initial pipeline's Run method should have been called")

	// Action: Delete the node configuration from KV store
	err = kv.Delete(key)
	require.NoError(t, err, "Delete node config from KV should not error")

	// Second synchronization: Detect deletion and stop the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (after delete) should not error")

	// Assertions for deletion
	assert.Equal(t, 1, pipelinesCreatedCount, "No new pipeline should be created on delete")

	assert.Eventually(t, func() bool {
		createdMockPipeline.mu.Lock()
		defer createdMockPipeline.mu.Unlock()
		return createdMockPipeline.stopCalled
	}, time.Second*1, time.Millisecond*10, "Pipeline's Stop method should have been called")

	// Check if the pipeline is removed from runningServices
	supervisor.servicesMutex.Lock()
	pipelineID := generatePipelineID(nodeCfg) // generatePipelineID needs to be accessible or redefined
	_, exists := supervisor.runningServices[pipelineID]
	supervisor.servicesMutex.Unlock()
	assert.False(t, exists, "Pipeline should be removed from runningServices map after deletion")
}

// TestSynchronizeServices_NodeDisabledEnabled tests that disabling and then re-enabling a node
// correctly stops and then starts/recreates the pipeline.
func TestSynchronizeServices_NodeDisabledEnabled(t *testing.T) {
	ctx := context.Background()

	// Setup NATS container
	natsContainer, err := tcnats.RunContainer(ctx, testcontainers.WithImage("nats:2.10-alpine"))
	require.NoError(t, err, "Failed to start NATS container")
	defer func() {
		if err := natsContainer.Terminate(ctx); err != nil {
			t.Fatalf("Failed to terminate NATS container: %s", err)
		}
	}()

	natsURL, err := natsContainer.ConnectionString(ctx)
	require.NoError(t, err, "Failed to get NATS connection string")

	nc, err := nats.Connect(natsURL)
	require.NoError(t, err, "Failed to connect to NATS container")
	defer nc.Close()

	js, err := nc.JetStream()
	require.NoError(t, err, "Failed to get JetStream context")

	kvStoreName := "node_configs"
	kv, err := js.CreateKeyValue(&nats.KeyValueConfig{Bucket: kvStoreName})
	require.NoError(t, err, "Failed to create KV store")

	const kvStoreKeyPrefix = "nodestore."

	supervisor, err := NewPipelineSupervisor(nc, kv, nil /*redisClient*/)
	require.NoError(t, err, "NewPipelineSupervisor should not error")
	supervisor.supervisorCtx = context.Background() // Initialize supervisorCtx for the test

	var currentMockPipeline *mockManagedPipeline
	pipelinesCreatedCount := 0
	var lastInitialNodes []common.NodeConfig

	originalNewManagedPipelineFunc := newManagedPipelineFunc
	newManagedPipelineFunc = func(parentCtx context.Context, network string, subnet string, vmType string, initialNodes []common.NodeConfig, natsConn *nats.Conn, redisClient decoder.RedisClient, statusUpdater NodeStatusUpdater) (ManagedPipelineInterface, error) {
		mockID := fmt.Sprintf("%s-%s-%s", strings.ToLower(network), strings.ToLower(subnet), strings.ToLower(vmType))
		mp := newMockManagedPipeline(mockID, initialNodes)
		currentMockPipeline = mp
		pipelinesCreatedCount++
		lastInitialNodes = initialNodes
		return mp, nil
	}
	defer func() { newManagedPipelineFunc = originalNewManagedPipelineFunc }()

	// 1. Initial Node Configuration (Enabled)
	nodeCfg := common.NodeConfig{
		ID:        "node-disable-enable-test-1",
		Network:   "testnet-de",
		Subnet:    "testsub-de",
		VMType:    "evm-de",
		IsEnabled: true,
		Name:      "Test Node Disable/Enable 1",
		HttpURL:   "http://localhost:11545",
	}
	key := kvStoreKeyPrefix + nodeCfg.ID
	initialData, _ := json.Marshal(nodeCfg)
	_, err = kv.Put(key, initialData)
	require.NoError(t, err, "Put initial enabled node config should not error")

	// First synchronization: Create and run the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (initial) should not error")

	require.NotNil(t, currentMockPipeline, "A pipeline should have been created initially")
	assert.Equal(t, 1, pipelinesCreatedCount, "Exactly one pipeline should be created initially")
	assert.Eventually(t, func() bool {
		currentMockPipeline.mu.Lock()
		defer currentMockPipeline.mu.Unlock()
		return currentMockPipeline.runCalled
	}, time.Second*1, time.Millisecond*10, "Initial pipeline's Run method should have been called")
	assert.False(t, currentMockPipeline.stopCalled, "Initial pipeline's Stop method should not have been called")
	require.Len(t, lastInitialNodes, 1, "Initial pipeline should have one node")
	assert.Equal(t, nodeCfg.ID, lastInitialNodes[0].ID, "Initial node ID mismatch")
	pipelineID := generatePipelineID(nodeCfg)
	supervisor.servicesMutex.Lock()
	_, exists := supervisor.runningServices[pipelineID]
	supervisor.servicesMutex.Unlock()
	assert.True(t, exists, "Pipeline should be in runningServices map initially")

	// 2. Disable the Node
	nodeCfg.IsEnabled = false
	disabledData, _ := json.Marshal(nodeCfg)
	_, err = kv.Put(key, disabledData) // Update with IsEnabled = false
	require.NoError(t, err, "Put disabled node config should not error")

	// Second synchronization: Detect disabled node and stop the pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (after disable) should not error")

	assert.Equal(t, 1, pipelinesCreatedCount, "No new pipeline should be created on disable")
	require.NotNil(t, currentMockPipeline, "Mock pipeline should still be the same instance")
	assert.True(t, currentMockPipeline.stopCalled, "Pipeline's Stop method should have been called after disable")
	// Check if UpdateNodeConfigs was called with zero enabled nodes before stop
	assert.Len(t, currentMockPipeline.updateNodeConfigsCalls, 1, "UpdateNodeConfigs should be called once for disable")
	if len(currentMockPipeline.updateNodeConfigsCalls) > 0 {
		assert.Empty(t, currentMockPipeline.updateNodeConfigsCalls[0], "UpdateNodeConfigs should be called with empty nodes for disable")
	}
	supervisor.servicesMutex.Lock()
	_, exists = supervisor.runningServices[pipelineID]
	supervisor.servicesMutex.Unlock()
	assert.False(t, exists, "Pipeline should be removed from runningServices map after disable")

	// Reset mock pipeline state for re-enable check (as a new one will be created)
	pipelinesCreatedCount = 0 // Reset count to check for new creation
	previousMockPipeline := currentMockPipeline
	currentMockPipeline = nil

	// 3. Re-enable the Node
	nodeCfg.IsEnabled = true
	enabledData, _ := json.Marshal(nodeCfg)
	_, err = kv.Put(key, enabledData) // Update with IsEnabled = true
	require.NoError(t, err, "Put re-enabled node config should not error")

	// Third synchronization: Detect re-enabled node and start a new pipeline
	err = supervisor.synchronizeServices(context.Background())
	require.NoError(t, err, "synchronizeServices (after re-enable) should not error")

	assert.Equal(t, 1, pipelinesCreatedCount, "A new pipeline should be created on re-enable")
	require.NotNil(t, currentMockPipeline, "A new pipeline instance should exist after re-enable")
	assert.NotSame(t, previousMockPipeline, currentMockPipeline, "A new pipeline instance should be created, not reusing the stopped one")
	assert.Eventually(t, func() bool {
		currentMockPipeline.mu.Lock()
		defer currentMockPipeline.mu.Unlock()
		return currentMockPipeline.runCalled
	}, time.Second*1, time.Millisecond*10, "Re-enabled pipeline's Run method should have been called")
	assert.False(t, currentMockPipeline.stopCalled, "Re-enabled pipeline's Stop method should not have been called yet")
	require.Len(t, lastInitialNodes, 1, "Re-enabled pipeline should have one node")
	assert.Equal(t, nodeCfg.ID, lastInitialNodes[0].ID, "Re-enabled node ID mismatch")
	supervisor.servicesMutex.Lock()
	_, exists = supervisor.runningServices[pipelineID]
	supervisor.servicesMutex.Unlock()
	assert.True(t, exists, "Pipeline should be back in runningServices map after re-enable")
}

// TODO: Add more tests for node updates, deletions, disabling, multiple nodes, etc.

func TestSynchronizeServices_MultipleNodesInGroup(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second) // Increased timeout for potentially more complex test
	defer cancel()

	// Test NATS setup
	natsContainer, err := tcnats.RunContainer(ctx, testcontainers.WithImage("nats:2.10-alpine"))
	require.NoError(t, err)
	defer func() {
		if err := natsContainer.Terminate(ctx); err != nil {
			t.Fatalf("failed to terminate NATS container: %s", err)
		}
	}()

	natsURL, err := natsContainer.ConnectionString(ctx)
	require.NoError(t, err)

	nc, err := nats.Connect(natsURL)
	require.NoError(t, err)
	defer nc.Close()

	js, err := nc.JetStream()
	require.NoError(t, err)

	kv, err := js.CreateKeyValue(&nats.KeyValueConfig{Bucket: "node_configs_multi"})
	require.NoError(t, err)

	// Mock pipeline setup
	var (
		pipelinesCreatedCount int
		lastInitialNodes      []common.NodeConfig
		currentMockPipeline   *mockManagedPipeline
		mockPipelineLock      sync.Mutex
	)

	originalNewManagedPipelineFunc := newManagedPipelineFunc
	newManagedPipelineFunc = func(
		pCtx context.Context, network, subnet, vmType string,
		initialNodes []common.NodeConfig,
		natsConn *nats.Conn,
		redisClient decoder.RedisClient, // Added redisClient
		statusUpdater NodeStatusUpdater,
	) (ManagedPipelineInterface, error) {
		mockPipelineLock.Lock()
		defer mockPipelineLock.Unlock()
		pipelinesCreatedCount++
		lastInitialNodes = make([]common.NodeConfig, len(initialNodes))
		copy(lastInitialNodes, initialNodes)
		pipelineCtx, pipelineCancel := context.WithCancel(pCtx) // pCtx is from the newManagedPipelineFunc signature
		mp := &mockManagedPipeline{
			id:                     generatePipelineID(initialNodes[0]), // Base ID on first node for simplicity
			nodes:                  append([]common.NodeConfig{}, initialNodes...),
			updateNodeConfigsCalls: make([][]common.NodeConfig, 0),
			wg:                     new(sync.WaitGroup),
			instanceCtx:            pipelineCtx,
			instanceCancel:         pipelineCancel,
		}
		oldInstanceAddr := currentMockPipeline // Capture before reassignment
		currentMockPipeline = mp
		log.Printf("Test newManagedPipelineFunc: Assigned new instance %p (id: %s) to currentMockPipeline. Old instance was %p.", mp, mp.id, oldInstanceAddr)
		return mp, nil
	}
	defer func() { newManagedPipelineFunc = originalNewManagedPipelineFunc }()

	// Supervisor setup
	// supCtx for supervisor, will be cancelled explicitly at the end of the test
	supCtx, supCancel := context.WithCancel(context.Background())
	// defer supCancel() // We will call supCancel explicitly before wg.Wait()

	// Define two nodes for the same group
	nodeCfg1 := common.NodeConfig{
		ID:        "node1-multi",
		Network:   "testnet-multi",
		Subnet:    "testsub-multi",
		VMType:    "evm-multi",
		IsEnabled: true,
		HttpURL:    "http://localhost:8545",
	}
	nodeCfg2 := common.NodeConfig{
		ID:        "node2-multi",
		Network:   "testnet-multi", // Same group
		Subnet:    "testsub-multi", // Same group
		VMType:    "evm-multi",     // Same group
		IsEnabled: true,
		HttpURL:    "http://localhost:8546",
	}

	const testKVStoreKeyPrefix = "nodestore."
	key1 := testKVStoreKeyPrefix + nodeCfg1.ID
	key2 := testKVStoreKeyPrefix + nodeCfg2.ID
	pipelineGroupID := generatePipelineID(nodeCfg1) // Group ID is the same for both

	// Initial state: Create pipeline with two nodes
	data1, _ := json.Marshal(nodeCfg1)
	_, err = kv.Put(key1, data1)
	require.NoError(t, err)
	data2, _ := json.Marshal(nodeCfg2)
	_, err = kv.Put(key2, data2)
	require.NoError(t, err)

	// Now start the supervisor, its initial synchronizeServices should pick up both nodes.
	supervisor, err := NewPipelineSupervisor(nc, kv, nil) // Using nil for RedisClient for now
	require.NoError(t, err, "NewPipelineSupervisor should not error")

	var supervisorWg sync.WaitGroup
	supervisorWg.Add(1)
	go func() {
		defer supervisorWg.Done()
		supervisor.Run(supCtx)
	}()

	// Wait for the pipeline to be created by the supervisor's initial sync
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		created := (pipelinesCreatedCount == 1 && currentMockPipeline != nil)
		mockPipelineLock.Unlock()
		return created
	}, 5*time.Second, 100*time.Millisecond, "Pipeline should be created by initial sync")

	// Now that the pipeline is confirmed to be created, access its details
	mockPipelineLock.Lock()
	assert.Equal(t, 1, pipelinesCreatedCount, "One pipeline should be created for the group")
	require.NotNil(t, currentMockPipeline, "A pipeline should have been created")
	assert.Len(t, lastInitialNodes, 2, "Pipeline should be initialized with two nodes")
	
	var foundNode1, foundNode2 bool
	for _, n := range lastInitialNodes {
		if n.ID == nodeCfg1.ID { foundNode1 = true }
		if n.ID == nodeCfg2.ID { foundNode2 = true }
	}
	assert.True(t, foundNode1, "Node1 should be in initial nodes")
	assert.True(t, foundNode2, "Node2 should be in initial nodes")

	assert.Eventually(t, func() bool {
		currentMockPipeline.mu.Lock()
		defer currentMockPipeline.mu.Unlock()
		return currentMockPipeline.runCalled
	}, time.Second*2, time.Millisecond*50, "Pipeline's Run method should have been called")
	mockPipelineLock.Unlock()

	supervisor.servicesMutex.Lock()
	_, exists := supervisor.runningServices[pipelineGroupID]
	supervisor.servicesMutex.Unlock()
	assert.True(t, exists, "Pipeline group should be in runningServices")

	// --- Test Scenario: Update one node in the group ---
	t.Log("Testing node update in multi-node group...")
	mockPipelineLock.Lock() // Lock to safely access currentMockPipeline
	// Reset updateCalled and capture current call count to ensure a new call is made
	initialUpdateCallCount := len(currentMockPipeline.updateNodeConfigsCalls)
	currentMockPipeline.updateCalled = false // Reset for this specific check
	mockPipelineLock.Unlock()

	updatedNodeCfg1 := nodeCfg1 // Create a new var to avoid modifying the original nodeCfg1 for later scenarios
	updatedNodeCfg1.HttpURL = "http://localhost:7777" // New distinct URL
	data1, err = json.Marshal(updatedNodeCfg1)
	require.NoError(t, err)
	_, err = kv.Put(key1, data1) // Update node1 in KV store (key1 corresponds to nodeCfg1.ID)
	require.NoError(t, err)

	// Manually publish to the 'nodes' subject to trigger the supervisor's event-based sync
	err = nc.Publish("nodes", nil) // nc is the *nats.Conn from test setup
	require.NoError(t, err, "Publishing to 'nodes' subject should not error")

	// Wait for supervisor to process the update and call UpdateNodeConfigs
	// The mock pipeline's UpdateNodeConfigs method sets updateCalled = true
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		// Check that updateCalled is true AND that a new call was registered if calls are appended
		// If updateNodeConfigsCalls is not strictly for new calls but all calls, then just check updateCalled
		// For now, assuming updateCalled is the primary flag for a recent call.
		updated := currentMockPipeline.updateCalled
		if len(currentMockPipeline.updateNodeConfigsCalls) > initialUpdateCallCount {
			updated = true // Also consider a new call entry as a sign of update
		}
		mockPipelineLock.Unlock()
		return updated
	}, 5*time.Second, 100*time.Millisecond, "UpdateNodeConfigs should be called after node update")

	mockPipelineLock.Lock()
	assert.True(t, currentMockPipeline.updateCalled, "mockManagedPipeline.updateCalled should be true after node update")
	// Ensure at least one new call was made. If UpdateNodeConfigs is called multiple times rapidly, this might need adjustment.
	require.GreaterOrEqual(t, len(currentMockPipeline.updateNodeConfigsCalls), initialUpdateCallCount+1, "UpdateNodeConfigs should have been called at least once more")
	
	lastUpdateArgs := currentMockPipeline.updateNodeConfigsCalls[len(currentMockPipeline.updateNodeConfigsCalls)-1]
	assert.Len(t, lastUpdateArgs, 2, "UpdateNodeConfigs should be called with 2 nodes after update")

	foundUpdatedNode1 := false
	foundNode2Unchanged := false // Renamed for clarity
	for _, cfg := range lastUpdateArgs {
		if cfg.ID == updatedNodeCfg1.ID && cfg.HttpURL == updatedNodeCfg1.HttpURL {
			foundUpdatedNode1 = true
		}
		if cfg.ID == nodeCfg2.ID && cfg.HttpURL == nodeCfg2.HttpURL { // nodeCfg2 is unchanged
			foundNode2Unchanged = true
		}
	}
	assert.True(t, foundUpdatedNode1, "Updated node1 (with new HttpURL) should be in UpdateNodeConfigs args")
	assert.True(t, foundNode2Unchanged, "Unchanged node2 should be in UpdateNodeConfigs args")
	currentMockPipeline.updateCalled = false // Reset for next potential scenario
	mockPipelineLock.Unlock()

	// --- Test Scenario: Disable node1 in the group ---
	t.Log("Testing disabling node1 in multi-node group...")
	mockPipelineLock.Lock()
	initialUpdateCallCount = len(currentMockPipeline.updateNodeConfigsCalls) // Recapture count
	currentMockPipeline.updateCalled = false
	initialStopCalled := currentMockPipeline.stopCalled // Check that pipeline is NOT stopped
	mockPipelineLock.Unlock()

	disabledNodeCfg1 := updatedNodeCfg1 // Continue from the previously updated state of nodeCfg1
	disabledNodeCfg1.IsEnabled = false
	data1, err = json.Marshal(disabledNodeCfg1)
	require.NoError(t, err)
	_, err = kv.Put(key1, data1) // Update node1 in KV store to be disabled
	require.NoError(t, err)

	// Manually publish to the 'nodes' subject to trigger the supervisor's event-based sync
	err = nc.Publish("nodes", nil)
	require.NoError(t, err, "Publishing to 'nodes' subject should not error")

	// Wait for supervisor to process the update and call UpdateNodeConfigs
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		updated := currentMockPipeline.updateCalled || len(currentMockPipeline.updateNodeConfigsCalls) > initialUpdateCallCount
		mockPipelineLock.Unlock()
		return updated
	}, 5*time.Second, 100*time.Millisecond, "UpdateNodeConfigs should be called after disabling node1")

	mockPipelineLock.Lock()
	assert.True(t, currentMockPipeline.updateCalled, "mockManagedPipeline.updateCalled should be true after disabling node1")
	require.GreaterOrEqual(t, len(currentMockPipeline.updateNodeConfigsCalls), initialUpdateCallCount+1, "UpdateNodeConfigs should have been called again after disabling node1")
	
	lastUpdateArgs = currentMockPipeline.updateNodeConfigsCalls[len(currentMockPipeline.updateNodeConfigsCalls)-1]
	// Only nodeCfg2 should be active now
	assert.Len(t, lastUpdateArgs, 1, "UpdateNodeConfigs should be called with 1 active node (nodeCfg2) after disabling node1")
	if len(lastUpdateArgs) == 1 {
		assert.Equal(t, nodeCfg2.ID, lastUpdateArgs[0].ID, "The remaining active node should be nodeCfg2")
		assert.True(t, lastUpdateArgs[0].IsEnabled, "The remaining node (nodeCfg2) should be enabled")
	}

	// Pipeline should NOT be stopped as nodeCfg2 is still active
	assert.Equal(t, initialStopCalled, currentMockPipeline.stopCalled, "Pipeline should NOT be stopped as one node is still active")
	currentMockPipeline.updateCalled = false // Reset for next scenario
	mockPipelineLock.Unlock()

	// --- Test Scenario: Disable node2 in the group (should stop the pipeline) ---
	t.Log("Testing disabling node2 in multi-node group (should stop pipeline)...")
	mockPipelineLock.Lock()
	initialUpdateCallCount = len(currentMockPipeline.updateNodeConfigsCalls) // Recapture count
	currentMockPipeline.updateCalled = false
	initialStopCalled = currentMockPipeline.stopCalled // Should be false before this step
	mockPipelineLock.Unlock()

	disabledNodeCfg2 := nodeCfg2 // nodeCfg2 was previously enabled
	disabledNodeCfg2.IsEnabled = false
	data2, err = json.Marshal(disabledNodeCfg2)
	require.NoError(t, err)
	_, err = kv.Put(key2, data2) // Update node2 in KV store to be disabled
	require.NoError(t, err)

	// Manually publish to the 'nodes' subject to trigger the supervisor's event-based sync
	err = nc.Publish("nodes", nil)
	require.NoError(t, err, "Publishing to 'nodes' subject should not error")

	// Wait for supervisor to process the update and call UpdateNodeConfigs
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		updated := currentMockPipeline.updateCalled || len(currentMockPipeline.updateNodeConfigsCalls) > initialUpdateCallCount
		mockPipelineLock.Unlock()
		return updated
	}, 5*time.Second, 100*time.Millisecond, "UpdateNodeConfigs should be called after disabling node2")

	mockPipelineLock.Lock()
	assert.True(t, currentMockPipeline.updateCalled, "mockManagedPipeline.updateCalled should be true after disabling node2")
	require.GreaterOrEqual(t, len(currentMockPipeline.updateNodeConfigsCalls), initialUpdateCallCount+1, "UpdateNodeConfigs should have been called again after disabling node2")
	
	lastUpdateArgs = currentMockPipeline.updateNodeConfigsCalls[len(currentMockPipeline.updateNodeConfigsCalls)-1]
	// Both nodes are now disabled, so UpdateNodeConfigs should be called with an empty list or nil
	assert.Empty(t, lastUpdateArgs, "UpdateNodeConfigs should be called with 0 active nodes after disabling node2")
	mockPipelineLock.Unlock()

	// Wait for the pipeline to be stopped
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		stopped := currentMockPipeline.stopCalled

		mockPipelineLock.Unlock()
		return stopped
	}, 5*time.Second, 100*time.Millisecond, "Pipeline should be stopped after all nodes are disabled")

	mockPipelineLock.Lock()
	assert.True(t, currentMockPipeline.stopCalled, "Pipeline should be stopped as no nodes are active")
	currentMockPipeline.updateCalled = false // Reset for next scenario
	mockPipelineLock.Unlock()

	// --- Test Scenario: Re-enable node1 (should create new pipeline) ---
	t.Log("Testing re-enabling node1 (should create new pipeline)...")
mockPipelineLock.Lock()
initialUpdateCallCount = len(currentMockPipeline.updateNodeConfigsCalls) // Recapture count
currentMockPipeline.updateCalled = false
initialStopCalled = currentMockPipeline.stopCalled // Check that pipeline is NOT stopped
mockPipelineLock.Unlock()

disabledNodeCfg1 = updatedNodeCfg1 // Continue from the previously updated state of nodeCfg1
disabledNodeCfg1.IsEnabled = false
data1, err = json.Marshal(disabledNodeCfg1)
require.NoError(t, err)
_, err = kv.Put(key1, data1) // Update node1 in KV store to be disabled
require.NoError(t, err)

// Manually publish to the 'nodes' subject to trigger the supervisor's event-based sync
err = nc.Publish("nodes", nil)
require.NoError(t, err, "Publishing to 'nodes' subject should not error")
	// At this point, both nodeCfg1 (as disabledNodeCfg1) and nodeCfg2 (as disabledNodeCfg2) are disabled in KV.
	// The previous pipeline instance was stopped.
	// We expect the factory to be called to create a new pipeline instance.
	mockPipelineLock.Lock()
	oldPipelineInstance := currentMockPipeline // Capture the reference to the (stopped) old pipeline instance
	mockPipelineLock.Unlock()

	reEnabledNodeCfg1 := disabledNodeCfg1 // This was nodeCfg1, but IsEnabled was false
	reEnabledNodeCfg1.IsEnabled = true
	data1, err = json.Marshal(reEnabledNodeCfg1)
	require.NoError(t, err)
	_, err = kv.Put(key1, data1) // Re-enable node1 in KV store
	require.NoError(t, err)

	// Manually publish to the 'nodes' subject to trigger the supervisor's event-based sync
	err = nc.Publish("nodes", nil)
	require.NoError(t, err, "Publishing to 'nodes' subject should not error")

	// Wait for the new pipeline to be created, run, and updated
	require.Eventually(t, func() bool {
		mockPipelineLock.Lock()
		defer mockPipelineLock.Unlock() // Ensure unlock happens even on panic or early return

		// Log current state for debugging
		log.Printf("Eventually check (re-enable node1): currentMockPipeline=%p, oldPipelineInstance=%p", currentMockPipeline, oldPipelineInstance)
		if currentMockPipeline != nil {
			log.Printf("Eventually check (re-enable node1): currentMockPipeline.id=%s, runCalled=%v, stopCalled=%v, updateCalled=%v, isStopped=%v", 
				currentMockPipeline.id, currentMockPipeline.runCalled, currentMockPipeline.stopCalled, currentMockPipeline.updateCalled, currentMockPipeline.IsStopped())
		} else {
			log.Printf("Eventually check (re-enable node1): currentMockPipeline is nil")
		}

		conditionMet := currentMockPipeline != nil &&
			currentMockPipeline != oldPipelineInstance &&
			currentMockPipeline.runCalled &&
			!currentMockPipeline.IsStopped() && // Use IsStopped() which handles its own lock for m.stopCalled
			currentMockPipeline.updateCalled
		
		return conditionMet
	}, 10*time.Second, 200*time.Millisecond, "New pipeline for re-enabled node1 should be created, running, and updated")

	mockPipelineLock.Lock()
	assert.NotNil(t, currentMockPipeline, "currentMockPipeline should point to the new instance")
	assert.NotEqual(t, oldPipelineInstance, currentMockPipeline, "A new pipeline instance should have been created")
	assert.True(t, currentMockPipeline.runCalled, "Newly created pipeline's Run method should be called")
	assert.False(t, currentMockPipeline.stopCalled, "Newly created pipeline should not be stopped")

	assert.True(t, currentMockPipeline.updateCalled, "UpdateNodeConfigs should be called on the new pipeline")
	// For a brand new pipeline, UpdateNodeConfigs is called once with the initial set of nodes.
	updateCalls := currentMockPipeline.updateNodeConfigsCalls
	numCalls := len(updateCalls)

	if numCalls == 1 {
		// Ideal case: UpdateNodeConfigs called exactly once.
		// No explicit log/assert here, subsequent checks will validate the call's content.
	} else if numCalls == 2 {
		// If called twice, check if they are identical.
		if !reflect.DeepEqual(updateCalls[0], updateCalls[1]) {
			assert.Fail(t, fmt.Sprintf("UpdateNodeConfigs called twice for new pipeline, and calls were different. Call 1: %v, Call 2: %v", updateCalls[0], updateCalls[1]))
		} else {
			// Log as a warning. The test will proceed, and subsequent checks on updateCalls[0] will still run.
			log.Printf("Warning: UpdateNodeConfigs was called twice for new pipeline, but calls were identical. First call: %v, Second call: %v", updateCalls[0], updateCalls[1])
		}
	} else {
		// If 0 calls or >2 calls (and not 2 identical), it's a failure against the expectation.
		// Subsequent checks on updateCalls[0] might panic if numCalls is 0, but this assert.Fail will catch it first.
		assert.Fail(t, fmt.Sprintf("UpdateNodeConfigs called %d times for new pipeline. Expected 1 (or 2 identical if a known issue). Calls: %v", numCalls, updateCalls))
	}
	
	lastUpdateArgs = currentMockPipeline.updateNodeConfigsCalls[0]
	assert.Len(t, lastUpdateArgs, 1, "UpdateNodeConfigs should be called with 1 active node (reEnabledNodeCfg1)")
	if len(lastUpdateArgs) == 1 {
		assert.Equal(t, reEnabledNodeCfg1.ID, lastUpdateArgs[0].ID, "The active node should be reEnabledNodeCfg1")
		assert.True(t, lastUpdateArgs[0].IsEnabled, "The active node (reEnabledNodeCfg1) should be enabled")
	}
	
	currentMockPipeline.updateCalled = false // Reset for the next scenario
	mockPipelineLock.Unlock()

	// TODO:
	// 5. Deleting nodeCfg1 -> pipeline still runs with nodeCfg2, UpdateNodeConfigs called.
	// 6. Deleting nodeCfg2 -> pipeline stops.

	// Teardown: Cancel supervisor context and wait for Run to exit before nc.Close() is deferred
	log.Println("TestSynchronizeServices_MultipleNodesInGroup: Signaling supervisor to shutdown...")
	supCancel() // Signal supervisor to stop
	log.Println("TestSynchronizeServices_MultipleNodesInGroup: Waiting for supervisor to shutdown...")
	supervisorWg.Wait() // Wait for supervisor's Run method to complete
	log.Println("TestSynchronizeServices_MultipleNodesInGroup: Supervisor shutdown complete.")
}
