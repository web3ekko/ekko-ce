package supervisor

import (
	"context"
	"errors"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

// kvStoreKeyPrefix is used for keys in the NATS KV store for node configurations.
const kvStoreKeyPrefix = "nodestore."

// newManagedPipelineFunc is a function variable that allows replacing the pipeline creation logic for testing.
var newManagedPipelineFunc = NewManagedPipeline




// PipelineSupervisor manages the lifecycle of blockchain data pipelines based on node configurations.
type PipelineSupervisor struct {
	natsConn         *nats.Conn
	kvStore          nats.KeyValue
	kvMutex          sync.Mutex                    // Mutex for KV store operations (e.g., in updateNodeStatusInKV)
	servicesMutex    sync.Mutex                    // Mutex for s.runningServices map
	runningServices  map[string]ManagedPipelineInterface   // Key: compositeKey (Network-Subnet-VMType), Value: ManagedPipeline instance
	supervisorCtx    context.Context               // Main context for the supervisor's operations
	supervisorCancel context.CancelFunc            // To cancel the supervisor's own context
	redisClient      decoder.RedisClient           // Redis client for EVM decoder in BlockFetcher
	// initWg           sync.WaitGroup              // Retained from previous checkpoint, if needed for startup synchronization
}

// NewPipelineSupervisor creates a new PipelineSupervisor.
func NewPipelineSupervisor(
	nc *nats.Conn,
	kv nats.KeyValue,
	redisClient decoder.RedisClient,
) (*PipelineSupervisor, error) {
	if nc == nil {
		return nil, fmt.Errorf("NATS connection cannot be nil")
	}
	if kv == nil {
		return nil, fmt.Errorf("NATS KV store cannot be nil")
	}

	return &PipelineSupervisor{
		natsConn:        nc,
		kvStore:         kv,
		runningServices: make(map[string]ManagedPipelineInterface),
		redisClient:     redisClient,
	}, nil
}

// Run starts the PipelineSupervisor's main loop, listening for context cancellation.
func (s *PipelineSupervisor) Run(ctx context.Context) error {
	log.Println("PipelineSupervisor: Starting...")
	s.supervisorCtx, s.supervisorCancel = context.WithCancel(ctx)
	defer s.supervisorCancel()

	if err := s.synchronizeServices(s.supervisorCtx); err != nil {
		log.Printf("Initial service synchronization failed: %v", err)
	}

	natsSubscription, err := s.natsConn.Subscribe("nodes", func(msg *nats.Msg) {
		log.Printf("PipelineSupervisor: Received event on subject '%s', triggering service synchronization.", msg.Subject)
		if err := s.synchronizeServices(s.supervisorCtx); err != nil {
			log.Printf("PipelineSupervisor: Error during event-triggered service synchronization: %v", err)
		}
	})
	if err != nil {
		log.Printf("PipelineSupervisor: Failed to subscribe to 'nodes' NATS subject: %v. Will rely on ticker only.", err)
	} else {
		log.Println("PipelineSupervisor: Subscribed to 'nodes' NATS subject for event-triggered synchronization.")
		defer func() {
			log.Println("PipelineSupervisor: Unsubscribing from 'nodes' NATS subject.")
			if err := natsSubscription.Unsubscribe(); err != nil {
				log.Printf("PipelineSupervisor: Error unsubscribing from 'nodes': %v", err)
			}
		}()
	}

	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	log.Println("PipelineSupervisor Run: Entering main loop.")
	for {
		select {
		case <-s.supervisorCtx.Done():
			log.Println("PipelineSupervisor: Context cancelled, shutting down services...")
			s.shutdownAllServices()
			log.Println("PipelineSupervisor: Shutdown complete.")
			return s.supervisorCtx.Err()
		case <-ticker.C:
			log.Println("PipelineSupervisor: Periodic check triggered, synchronizing services...")
			if err := s.synchronizeServices(s.supervisorCtx); err != nil {
				log.Printf("PipelineSupervisor: Error during periodic service synchronization: %v", err)
			}
		}
	}
}

// synchronizeServices fetches all node configurations from the KV store and reconciles running services.
func (s *PipelineSupervisor) synchronizeServices(ctx context.Context) error {
	log.Println("PipelineSupervisor: Synchronizing services...")
	s.servicesMutex.Lock()
	defer s.servicesMutex.Unlock()

	keys, err := s.kvStore.Keys() // This gets all keys, not just those with kvStoreKeyPrefix
	if err != nil {
		if errors.Is(err, nats.ErrNoKeysFound) {
			log.Println("PipelineSupervisor: No keys found in KV store (or bucket is empty), treating as zero active nodes.")
			keys = []string{} // Ensure keys is an empty slice so downstream logic sees no nodes
			// No error returned, proceed to reconcile with zero active nodes
		} else {
			// It's a different error, so report it
			log.Printf("PipelineSupervisor: Error fetching keys from KV store: %v", err)
			return fmt.Errorf("error fetching keys from KV store: %w", err)
		}
	}

	// 1. Group NodeConfigs by Network+Subnet+VMType.
	groupedNodeConfigs := make(map[string][]common.NodeConfig)
	for _, key := range keys {
		// Ensure we only process keys relevant to node configurations if a prefix is used elsewhere.
		// For now, assuming all keys in this KV store are node configs or this check is handled by prefix on Get.
		// If kvStoreKeyPrefix is defined and used for Put, Keys() might return unprefixed keys or this needs filtering.
		// For simplicity, assuming 'key' is the direct key used in s.kvStore.Get() for node configs.
		// If nodeID in updateNodeStatusInKV is UUID, and keyInKV = kvStoreKeyPrefix + nodeID, then keys here should match that pattern.
		if !strings.HasPrefix(key, kvStoreKeyPrefix) { // Assuming kvStoreKeyPrefix is defined globally or on 's'
			// log.Printf("PipelineSupervisor: Skipping key %s as it does not match node config prefix %s", key, kvStoreKeyPrefix)
			continue // Skip keys not matching our pattern if prefix is used consistently
		}

		entry, errK := s.kvStore.Get(key)
		if errK != nil {
			log.Printf("PipelineSupervisor: Error fetching entry for key %s: %v", key, errK)
			continue
		}
		var nodeCfg common.NodeConfig
		if errJ := json.Unmarshal(entry.Value(), &nodeCfg); errJ != nil {
			log.Printf("PipelineSupervisor: Error unmarshalling node config for key %s: %v", key, errJ)
			continue
		}

		if nodeCfg.IsEnabled {
			pipelineID := generatePipelineID(nodeCfg)
			groupedNodeConfigs[pipelineID] = append(groupedNodeConfigs[pipelineID], nodeCfg)
		}
	}

	log.Printf("PipelineSupervisor: Found %d active pipeline groups from KV store.", len(groupedNodeConfigs))

	currentPipelineIDs := make(map[string]bool)

	// 2. For each group, create or update a ManagedPipeline instance.
	for pipelineID, nodesInGroup := range groupedNodeConfigs {
		currentPipelineIDs[pipelineID] = true
		if len(nodesInGroup) == 0 { // Should not happen if only IsEnabled nodes are added
			continue
		}

		if existingPipeline, ok := s.runningServices[pipelineID]; ok {
			// Pipeline exists, update its node configurations
			log.Printf("PipelineSupervisor: Updating existing pipeline %s with %d nodes.", pipelineID, len(nodesInGroup))
			err := existingPipeline.UpdateNodeConfigs(nodesInGroup)
			if err != nil {
				log.Printf("PipelineSupervisor: Error updating node configs for pipeline %s: %v", pipelineID, err)
			}
		} else {
			// Pipeline does not exist, create and start a new one
			log.Printf("PipelineSupervisor: Creating new pipeline %s for %d nodes.", pipelineID, len(nodesInGroup))
			// Extract network, subnet, vmType from the first node (they are the same for the group)
			firstNode := nodesInGroup[0]
			newPipeline, err := newManagedPipelineFunc(
				s.supervisorCtx, // Pass the supervisor's main context
				firstNode.Network,
				firstNode.Subnet,
				firstNode.VMType,
				nodesInGroup,
				s.natsConn,
				s.redisClient,
				s.updateNodeStatusInKV, // Pass the callback method
			)
			if err != nil {
				log.Printf("PipelineSupervisor: Error creating new pipeline %s: %v", pipelineID, err)
				continue
			}
			s.runningServices[pipelineID] = newPipeline

			// Call UpdateNodeConfigs for the new pipeline with its initial set of nodes
			if err := newPipeline.UpdateNodeConfigs(nodesInGroup); err != nil {
				log.Printf("PipelineSupervisor: Error initially configuring new pipeline %s: %v", pipelineID, err)
				// Decide if we should continue without this pipeline or remove it
				delete(s.runningServices, pipelineID) // Example: remove if initial config fails
				continue
			}

			go newPipeline.Run() // Run the pipeline in a new goroutine
			log.Printf("PipelineSupervisor: Started new pipeline %s after initial configuration.", pipelineID)
		}
	}

	// 3. Stop ManagedPipelines for groups that no longer exist or have no enabled nodes.
	for pipelineID, managedPipeline := range s.runningServices {
		if !currentPipelineIDs[pipelineID] {
			activeNodesInGroup := groupedNodeConfigs[pipelineID]
			log.Printf("PipelineSupervisor: Pipeline %s no longer active or has no enabled nodes. Updating with %d nodes before stopping.", pipelineID, len(activeNodesInGroup))
			managedPipeline.UpdateNodeConfigs(activeNodesInGroup) // Inform the pipeline it has no active nodes

			log.Printf("PipelineSupervisor: Stopping pipeline %s...", pipelineID)
			managedPipeline.Stop() // This should handle context cancellation and cleanup
			delete(s.runningServices, pipelineID)
			log.Printf("PipelineSupervisor: Pipeline %s stopped and removed.", pipelineID)
		}
	}

	log.Printf("PipelineSupervisor: Service synchronization complete. %d pipelines running.", len(s.runningServices))
	return nil
}

// shutdownAllServices iterates over running services and signals them to stop.
func (s *PipelineSupervisor) shutdownAllServices() {
	log.Println("PipelineSupervisor: Initiating shutdown of all managed services...")
	// s.kvMutex.Lock() // Lock if modifying runningServices map concurrently, though usually called in sequence
	// defer s.kvMutex.Unlock()

	var wg sync.WaitGroup
	for id, pipeline := range s.runningServices {
		wg.Add(1)
		go func(pid string, p ManagedPipelineInterface) {
			defer wg.Done()
			log.Printf("PipelineSupervisor: Stopping pipeline %s...", pid)
			if p != nil {
				p.Stop()
				p.Wait()
			}
			log.Printf("PipelineSupervisor: Pipeline %s stopped.", pid)
		}(id, pipeline)
	}
	wg.Wait()
	// delete(s.runningServices, id) // Temporarily removed, will be handled by ManagedPipeline's lifecycle
	log.Println("PipelineSupervisor: All services have been signaled to stop and are shutting down.")
}

// generatePipelineID creates a unique identifier for a pipeline based on network, subnet, and VM type.
func generatePipelineID(nodeCfg common.NodeConfig) string {
	return fmt.Sprintf("%s-%s-%s",
		strings.ToLower(nodeCfg.Network),
		strings.ToLower(nodeCfg.Subnet),
		strings.ToLower(nodeCfg.VMType),
	)
}

// updateNodeStatusInKV fetches a node's configuration from the KV store, updates its status fields,
// and writes it back. This will trigger a NATS event which in turn causes synchronizeServices.
// The nodeID here is the actual key in the KV store (e.g., the UUID of the node).
func (s *PipelineSupervisor) updateNodeStatusInKV(nodeID string, status string, errMsg string) error {
	s.kvMutex.Lock()
	defer s.kvMutex.Unlock()

	keyInKV := kvStoreKeyPrefix + nodeID // If nodeID is already the full key, prefix might be empty.

	entry, err := s.kvStore.Get(keyInKV)
	if err != nil {
		if err == nats.ErrKeyNotFound {
			log.Printf("PipelineSupervisor: Cannot update status for node %s (key: %s), not found in KV store.", nodeID, keyInKV)
			return fmt.Errorf("node %s (key: %s) not found in KV store: %w", nodeID, keyInKV, err)
		}
		log.Printf("PipelineSupervisor: Error fetching node %s (key: %s) from KV store for status update: %v", nodeID, keyInKV, err)
		return fmt.Errorf("failed to get node %s (key: %s) from KV store: %w", nodeID, keyInKV, err)
	}

	var nodeCfg common.NodeConfig
	if err := json.Unmarshal(entry.Value(), &nodeCfg); err != nil {
		log.Printf("PipelineSupervisor: Error unmarshalling node %s (key: %s) for status update: %v", nodeID, keyInKV, err)
		return fmt.Errorf("failed to unmarshal node %s (key: %s): %w", nodeID, keyInKV, err)
	}

	// Update status fields
	previousStatus := nodeCfg.Status
	nodeCfg.Status = status
	nodeCfg.LastStatusUpdate = time.Now().UTC().Format(time.RFC3339)

	if errMsg != "" {
		nodeCfg.LastError = errMsg
	} else if status == common.NodeStatusActive { // Clear error if status is now Active
		nodeCfg.LastError = ""
	}

	// Avoid unnecessary KV writes if status and error message haven't changed meaningfully
	// Only skip if status is the same AND (either no error OR the same error message)
	if previousStatus == nodeCfg.Status && ((errMsg == "" && nodeCfg.LastError == "") || (errMsg != "" && nodeCfg.LastError == errMsg)) {
		// Log this decision but still update LastStatusUpdate by proceeding with the write
		log.Printf("PipelineSupervisor: Node %s status '%s' and error '%s' effectively unchanged. Will still update timestamp.", nodeID, status, errMsg)
	}

	updatedJSON, err := json.Marshal(nodeCfg)
	if err != nil {
		log.Printf("PipelineSupervisor: Error marshalling updated node %s (key: %s) for status update: %v", nodeID, keyInKV, err)
		return fmt.Errorf("failed to marshal updated node %s (key: %s): %w", nodeID, keyInKV, err)
	}

	if _, err := s.kvStore.Put(keyInKV, updatedJSON); err != nil {
		log.Printf("PipelineSupervisor: Error writing updated node %s (key: %s) to KV store: %v", nodeID, keyInKV, err)
		return fmt.Errorf("failed to put updated node %s (key: %s) to KV store: %w", nodeID, keyInKV, err)
	}

	log.Printf("PipelineSupervisor: Updated status for node %s (key: %s) to '%s'. Error: '%s'", nodeID, keyInKV, status, errMsg)
	return nil
}

// startNodeServices launches the necessary services (NewHeadListener, etc.) for a given node.
// ctx is s.supervisorCtx
func (s *PipelineSupervisor) startNodeServices(ctx context.Context, nodeCfg common.NodeConfig, serviceIdentifier string) {
	/* --- OLD LOGIC - TO BE REPLACED BY ManagedPipeline --- 
	// Create a new context for this specific service (or group of services for a node)
	// This allows individual cancellation of a service without stopping the entire supervisor.
	childCtx, childCancel := context.WithCancel(ctx) // Use the passed-down supervisor's context as parent
	// s.runningServices[serviceIdentifier] = childCancel // Store the cancel func to stop it later - Now map[string]*ManagedPipeline

	log.Printf("Starting services for node: %s (ID: %s, Network: %s, VM: %s)", nodeCfg.Name, nodeCfg.ID, nodeCfg.Network, nodeCfg.VMType)

	// Example: Launching a NewHeadListener
	// Adjust according to actual service components and their needs.
	// listener := listeners.NewNewHeadListener(nodeCfg, s.natsConn) // Assuming NewHeadListener is adapted or replaced
	// BlockFetchers might be managed per VMType rather than per node if they subscribe to a wildcard subject.
	--- END OLD LOGIC --- */
	log.Printf("PipelineSupervisor: startNodeServices for %s called (currently a stub). Logic to be replaced by ManagedPipeline management.", serviceIdentifier)
}
