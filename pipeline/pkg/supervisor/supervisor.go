package supervisor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/nats-io/nats.go"
	// "github.com/web3ekko/ekko-ce/pipeline/internal/config" // Assuming config path
	"github.com/web3ekko/ekko-ce/pipeline/pkg/listeners" // Added for NewHeadListener
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"    // For common.NodeConfig
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"  // For decoder.RedisClient
)

// PipelineSupervisor manages the lifecycle of NewHeadListener and BlockFetcher services.
type PipelineSupervisor struct {
	natsConn         *nats.Conn
	kvStore          nats.KeyValue                 // NATS Key-Value store for node configurations
	runningServices  map[string]context.CancelFunc // Key: serviceIdentifier (e.g., nodeID or nodeID_vmType), Value: cancel function
	supervisorCtx    context.Context               // Main context for the supervisor's operations
	supervisorCancel context.CancelFunc            // To cancel the supervisor's own context
	// config   config.Config // General pipeline configuration
	redisClient      decoder.RedisClient           // Redis client for EVM decoder in BlockFetcher
}

// NewPipelineSupervisor creates a new supervisor instance.
func NewPipelineSupervisor(natsURL string, redisClient decoder.RedisClient /*cfg config.Config*/) (*PipelineSupervisor, error) {
	nc, err := nats.Connect(natsURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to NATS at %s: %w", natsURL, err)
	}

	// Get JetStream context
	js, err := nc.JetStream()
	if err != nil {
		nc.Close()
		return nil, fmt.Errorf("failed to get NATS JetStream context: %w", err)
	}

	kv, err := js.KeyValue("ekko_nodes") // Use the actual KV bucket name defined in your API
	if err != nil {
		nc.Close() // Close connection if KV store setup fails
		return nil, fmt.Errorf("failed to get NATS KV store 'ekko_nodes': %w", err)
	}

	return &PipelineSupervisor{
		natsConn:        nc,
		kvStore:         kv,
		// config:   cfg,
		runningServices: make(map[string]context.CancelFunc),
		redisClient:     redisClient,
	}, nil
}

// Run starts the supervisor's main loop, periodically checking node configurations
// and managing the associated services.
func (s *PipelineSupervisor) Run(ctx context.Context) error {
	log.Println("PipelineSupervisor Run: Starting...")
	s.supervisorCtx, s.supervisorCancel = context.WithCancel(ctx) // Create cancellable context for supervisor's own lifetime

	defer func() {
		log.Println("PipelineSupervisor Run: Deferred shutdown actions starting...")
		s.shutdownAllServices() // Gracefully stop all managed goroutines

		if s.supervisorCancel != nil {
			log.Println("PipelineSupervisor Run: Cancelling supervisor's internal context.")
			s.supervisorCancel() // Cancel the supervisor's own context
		}
		if s.natsConn != nil {
			log.Println("PipelineSupervisor Run: Closing NATS connection.")
			s.natsConn.Close() // Ensure NATS connection is closed on exit
		}
		log.Println("PipelineSupervisor Run: Fully stopped.")
	}()

	// Perform an initial synchronization of services when the supervisor starts.
	if err := s.synchronizeServices(s.supervisorCtx); err != nil { // Pass down the supervisor's cancellable context
		log.Printf("Initial service synchronization failed: %v", err)
		// For now, we'll log and continue. Consider if this should be fatal.
	}

	// Ticker for periodic checks.
	ticker := time.NewTicker(30 * time.Second) // Example: check every 30 seconds
	defer ticker.Stop()

	log.Println("PipelineSupervisor Run: Entering main loop.")
	for {
		select {
		case <-ctx.Done(): // Main context from the caller is done (e.g., OS signal)
			log.Println("PipelineSupervisor Run: Main context cancelled by caller. Initiating shutdown...")
			return ctx.Err() // Propagate the cancellation error

		case <-s.supervisorCtx.Done(): // Supervisor's internal context is done (e.g., self-initiated shutdown or error)
			log.Println("PipelineSupervisor Run: Supervisor's internal context cancelled.")
			return s.supervisorCtx.Err()

		case <-ticker.C:
			log.Println("PipelineSupervisor Run: Tick. Time to synchronize services.")
			if err := s.synchronizeServices(s.supervisorCtx); err != nil { // Pass down the supervisor's cancellable context
				log.Printf("Error during service synchronization: %v", err)
			}
		}
	}
}

// synchronizeServices fetches the current node configurations from NATS KV
// and starts, stops, or updates services as necessary.
// ctx here is s.supervisorCtx
func (s *PipelineSupervisor) synchronizeServices(ctx context.Context) error {
	log.Println("Synchronizing services with NATS KV store...")

	// 1. Get all node configuration keys from the KV store.
	keys, err := s.kvStore.Keys()
	if err != nil {
		return fmt.Errorf("failed to list keys from NATS KV store 'ekko_nodes': %w", err)
	}
	log.Printf("Found %d keys in KV store: %v", len(keys), keys)


	currentDesiredServices := make(map[string]common.NodeConfig) // Stores configs of nodes that should have active services

	// 2. For each key, get the node configuration.
	for _, key := range keys {
		entry, err := s.kvStore.Get(key)
		if err != nil {
			log.Printf("Error fetching KV entry for key %s: %v", key, err)
			continue // Skip this node, or handle error more robustly
		}

		var nodeCfg common.NodeConfig
		if err := json.Unmarshal(entry.Value(), &nodeCfg); err != nil {
			log.Printf("Error unmarshalling node config for key %s (value: %s): %v", key, string(entry.Value()), err)
			continue // Skip malformed entries
		}
		
		log.Printf("Processing node config: ID=%s, Name=%s, Network=%s, VMType=%s, IsEnabled=%t",
			nodeCfg.ID, nodeCfg.Name, nodeCfg.Network, nodeCfg.VMType, nodeCfg.IsEnabled)

		if nodeCfg.IsEnabled {
			serviceIdentifier := nodeCfg.ID // Assuming ID is unique and sufficient for now
			currentDesiredServices[serviceIdentifier] = nodeCfg

			if _, isRunning := s.runningServices[serviceIdentifier]; !isRunning {
				log.Printf("Attempting to start services for enabled node: %s (ID: %s, VM: %s)", nodeCfg.Name, nodeCfg.ID, nodeCfg.VMType)
				s.startNodeServices(ctx, nodeCfg, serviceIdentifier) // Pass down the supervisor's context
			} else {
				// TODO: Handle updates to existing services if config changed (e.g., WSS URL)
				// This might involve stopping and restarting the specific service.
				log.Printf("Services for node %s (ID: %s) already running. (Update logic TBD)", nodeCfg.Name, serviceIdentifier)
			}
		}
	}

	// 3. Stop services for nodes that are no longer in the KV store, are marked as disabled, or whose configs led to errors.
	for serviceID, cancelFunc := range s.runningServices {
		if _, stillDesired := currentDesiredServices[serviceID]; !stillDesired {
			log.Printf("Attempting to stop services for service ID: %s (node removed, disabled, or config error)", serviceID)
			if cancelFunc != nil {
				cancelFunc() // Trigger the context cancellation for the service goroutines
			}
			delete(s.runningServices, serviceID)
		}
	}

	return nil
}

// startNodeServices launches the necessary services (NewHeadListener, etc.) for a given node.
// ctx is s.supervisorCtx
func (s *PipelineSupervisor) startNodeServices(ctx context.Context, nodeCfg common.NodeConfig, serviceIdentifier string) {
	log.Printf("startNodeServices: Launching services for %s (ID: %s)", nodeCfg.Name, serviceIdentifier)
	// Create a new context that can be cancelled independently for this specific service/node.
	childCtx, childCancel := context.WithCancel(ctx)
	s.runningServices[serviceIdentifier] = childCancel

	// Start NewHeadListener for this node
	listener := listeners.NewNewHeadListener(nodeCfg, s.natsConn)
	go func() {
		log.Printf("Supervisor: NewHeadListener goroutine starting for node %s (ID: %s, WSS: %s)", nodeCfg.Name, nodeCfg.ID, nodeCfg.WssURL)
		if err := listener.Run(childCtx); err != nil && err != context.Canceled {
			log.Printf("Supervisor: NewHeadListener for node %s (ID: %s) exited with error: %v", nodeCfg.Name, nodeCfg.ID, err)
			// The service's context (childCtx) will be cancelled by the supervisor if the node is disabled/removed.
			// If the listener exits due to an internal error not context.Canceled, it will stop.
			// The supervisor's periodic sync might attempt to restart it if the node config is still valid and enabled.
			// Consider adding logic here or in the listener to manage s.runningServices entry upon self-termination.
		}
		log.Printf("Supervisor: NewHeadListener goroutine stopped for node %s (ID: %s)", nodeCfg.Name, nodeCfg.ID)
	}()

	// TODO: Start BlockFetcher for this node's VMType if not already running.
	// BlockFetchers might be managed per VMType rather than per node if they subscribe to a wildcard subject.
}

// shutdownAllServices gracefully stops all services managed by the supervisor.
func (s *PipelineSupervisor) shutdownAllServices() {
	log.Println("shutdownAllServices: Initiating shutdown of all managed services...")
	count := 0
	for id, cancel := range s.runningServices {
		log.Printf("shutdownAllServices: Sending stop signal to service %s...", id)
		if cancel != nil {
			cancel() // Signal the service's context to be cancelled
			count++
		}
	}
	// Note: This doesn't wait for goroutines to actually finish, just signals them.
	// For a more robust shutdown, a sync.WaitGroup could be used in startNodeServices
	// and waited upon here after all cancel() calls.
	log.Printf("shutdownAllServices: All %d active services signaled to stop.", count)
}
