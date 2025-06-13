package supervisor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder" // For RedisClient if BlockFetcher needs it

	// We will likely use blockchain.WebSocketSource directly or adapt it
	"github.com/web3ekko/ekko-ce/pipeline/pkg/blockchain"
	// For transaction persistence to Arrow files
	"github.com/web3ekko/ekko-ce/pipeline/pkg/persistence"
)

// NodeStatusUpdater defines the callback function signature for updating node status.
// It's typically implemented by a method in PipelineSupervisor.
type NodeStatusUpdater func(nodeID string, status string, errMsg string) error

// ManagedPipelineInterface defines the operations a PipelineSupervisor can perform on a managed pipeline.
type ManagedPipelineInterface interface {
	Run() error
	Stop()
	Wait()
	UpdateNodeConfigs(newNodes []common.NodeConfig) error
	// ID returns the unique identifier of the pipeline (e.g., network-subnet-vmtype)
	// This might be useful for logging or identification from the supervisor side if needed.
	// ID() string
}

// HeadSource defines an interface for components that provide a stream of blockchain head data.
// This allows ManagedPipeline to be agnostic to the specific source implementation (e.g., WebSocketSource, or a future type).
type HeadSource interface {
	Start(ctx context.Context) error // Starts the source; may launch goroutines. The context is for the source's own long-running operations if any.
	Out() <-chan interface{}         // Returns a channel from which block data (e.g., *blockchain.Block) can be read.
	Close() error                    // Stops the source and cleans up resources.
	// UpdateEndpoints allows changing the WSS and HTTP endpoints the source connects to.
	// This might involve reconnecting or reinitializing the source.
	UpdateEndpoints(websocketURL string, httpURL string) error
}

// WebSocketSourceAdapter adapts blockchain.WebSocketSource to the HeadSource interface.
// It also manages the lifecycle of the underlying WebSocketSource more explicitly with context.
type WebSocketSourceAdapter struct {
	ws      *blockchain.WebSocketSource
	mu      sync.Mutex
	wssURL  string
	httpURL string
	// ctx     context.Context // Context for the adapter's own operations, if needed beyond what ws.Start provides
	// cancel  context.CancelFunc
}

// NewWebSocketSourceAdapter creates a new adapter for the blockchain.WebSocketSource.
func NewWebSocketSourceAdapter(wssURL, httpURL string) *WebSocketSourceAdapter {
	return &WebSocketSourceAdapter{
		wssURL:  wssURL,
		httpURL: httpURL,
		// ws: blockchain.NewWebSocketSource(wssURL, httpURL), // Initialize ws in Start or UpdateEndpoints
	}
}

// Start initializes and starts the underlying WebSocketSource.
// The provided context is for the Start operation itself, not necessarily for long-running operations
// of the WebSocketSource, which manages its own lifecycle via its internal context passed to its goroutine.
func (a *WebSocketSourceAdapter) Start(ctx context.Context) error {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.ws != nil {
		// If already started, potentially stop and restart, or return error/ignore.
		// For now, let's assume Start is called once or after a Close/UpdateEndpoints that nilled a.ws.
		log.Printf("WebSocketSourceAdapter: Start called but ws already exists for %s. Re-creating.", a.wssURL)
		a.ws.Close() // Ensure old one is closed
	}

	log.Printf("WebSocketSourceAdapter: Initializing and starting new WebSocketSource for WSS: %s, HTTP: %s", a.wssURL, a.httpURL)
	a.ws = blockchain.NewWebSocketSource(a.wssURL, a.httpURL)
	err := a.ws.Start() // blockchain.WebSocketSource.Start() currently doesn't take a context.
	if err != nil {
		log.Printf("WebSocketSourceAdapter: Failed to start underlying WebSocketSource for %s: %v", a.wssURL, err)
		return fmt.Errorf("failed to start underlying WebSocketSource for %s: %w", a.wssURL, err)
	}
	log.Printf("WebSocketSourceAdapter: Underlying WebSocketSource started for %s", a.wssURL)
	return nil
}

// Out returns the output channel of the underlying WebSocketSource.
func (a *WebSocketSourceAdapter) Out() <-chan interface{} {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ws == nil {
		// Return a closed channel or nil if not started to prevent blocking
		closedCh := make(chan interface{})
		close(closedCh)
		return closedCh
	}
	return a.ws.Out()
}

// Close stops the underlying WebSocketSource.
func (a *WebSocketSourceAdapter) Close() error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.ws != nil {
		log.Printf("WebSocketSourceAdapter: Closing underlying WebSocketSource for %s", a.wssURL)
		err := a.ws.Close()
		a.ws = nil // Mark as closed/nil
		return err
	}
	return nil
}

// UpdateEndpoints reconfigures the adapter with new URLs.
// This will typically close the existing connection and establish a new one.
func (a *WebSocketSourceAdapter) UpdateEndpoints(websocketURL string, httpURL string) error {
	a.mu.Lock()
	log.Printf("WebSocketSourceAdapter: Updating endpoints. Old WSS: %s, New WSS: %s", a.wssURL, websocketURL)
	a.wssURL = websocketURL
	a.httpURL = httpURL
	// Mark the current ws as needing restart by nilling it. The actual restart happens on next Start call by ManagedPipeline.
	// Or, we could try to restart it here if ManagedPipeline expects immediate effect.
	// For now, let ManagedPipeline's Run loop or UpdateNodeConfigs handle the restart logic via Close() then Start().
	if a.ws != nil {
		a.ws.Close() // Close the old connection
		a.ws = nil   // Nullify to indicate it needs re-starting
	}
	a.mu.Unlock()
	// The caller (ManagedPipeline) will need to call Start() again on this adapter.
	return nil
}

// ManagedPipeline represents an active pipeline for a specific network/subnet/vm_type combination.
type ManagedPipeline struct {
	id               string // Composite key: Network-Subnet-VMType
	network          string
	subnet           string
	vmType           string
	nodeConfigs      []common.NodeConfig // All current active NodeConfigs for this pipeline
	activeNodeConfig common.NodeConfig   // The NodeConfig currently being used
	natsConn         *nats.Conn
	redisClient      decoder.RedisClient // Or the adapter for BlockFetcher if used
	statusUpdater    NodeStatusUpdater   // Callback to PipelineSupervisor.updateNodeStatusInKV

	source HeadSource // Abstracted source
	// sink    *ekkoPipeline.NATSSink // Re-use or adapt NATSSink - We will publish directly using natsConn for now

	ctx         context.Context
	cancel      context.CancelFunc       // For canceling the context
	wg          sync.WaitGroup           // For synchronizing goroutines
	arrowWriter *persistence.ArrowWriter // For transaction persistence
}

// NewManagedPipeline creates and initializes a new ManagedPipeline instance.
func NewManagedPipeline(
	parentCtx context.Context, // Context from the supervisor
	network string,
	subnet string,
	vmType string,
	initialNodes []common.NodeConfig,
	natsConn *nats.Conn,
	redisClient decoder.RedisClient, // Pass RedisClient, even if source doesn't use it directly
	statusUpdater NodeStatusUpdater,
) (ManagedPipelineInterface, error) {
	if len(initialNodes) == 0 {
		return nil, fmt.Errorf("cannot create ManagedPipeline for %s-%s-%s with no nodes", network, subnet, vmType)
	}

	// Configure and initialize the ArrowWriter for transaction persistence
	// Get MinIO configuration from environment variables
	endpoint := getEnvWithDefault("MINIO_ENDPOINT", "localhost:9000")
	accessKey := getEnvWithDefault("MINIO_ACCESS_KEY", "minioadmin")
	secretKey := getEnvWithDefault("MINIO_SECRET_KEY", "minioadmin")
	bucketName := getEnvWithDefault("MINIO_BUCKET", "blockchain-data")
	useSSL := getEnvBoolWithDefault("MINIO_USE_SSL", false)

	// Configure MinIO for ArrowWriter
	minioConfig := persistence.MinioConfig{
		Endpoint:   endpoint,
		AccessKey:  accessKey,
		SecretKey:  secretKey,
		UseSSL:     useSSL,
		BucketName: bucketName,
		BasePath:   "transactions", // Base path for Arrow files
	}

	// Initialize MinIO storage - ensureBucketExists is called automatically in NewMinioStorage
	_, err := persistence.NewMinioStorage(minioConfig)
	if err != nil {
		log.Printf("NewManagedPipeline: Failed to initialize MinIO storage: %v", err)
		return nil, fmt.Errorf("failed to initialize MinIO storage: %w", err)
	}

	log.Printf("NewManagedPipeline: Successfully connected to MinIO and ensured bucket %s exists", bucketName)

	arrowWriterConfig := persistence.ArrowWriterConfig{
		BatchSize:     25,               // Default batch size, can be made configurable
		FlushInterval: 10 * time.Second, // Default flush interval, can be made configurable
		MinioConfig:   minioConfig,
		NatsURL:       natsConn.ConnectedUrl(), // Use the current NATS connection URL
		NatsSubjectPattern: fmt.Sprintf("ekko.%s.%s.%s.persistence",
			strings.ToLower(network),
			strings.ToLower(subnet),
			strings.ToLower(vmType)),
	}

	arrowWriter, err := persistence.NewArrowWriter(arrowWriterConfig)
	if err != nil {
		log.Printf("NewManagedPipeline: Failed to create ArrowWriter for network=%s subnet=%s vm_type=%s: %v",
			network, subnet, vmType, err)
		return nil, fmt.Errorf("failed to create ArrowWriter: %w", err)
	}

	mpCtx, mpCancel := context.WithCancel(parentCtx)
	pipelineID := fmt.Sprintf("%s-%s-%s", strings.ToLower(network), strings.ToLower(subnet), strings.ToLower(vmType))

	// Select the first enabled node as active. A more sophisticated selection might be needed later.
	var activeNode common.NodeConfig
	foundActive := false
	for _, node := range initialNodes {
		if node.IsEnabled {
			activeNode = node
			foundActive = true
			break
		}
	}
	if !foundActive {
		mpCancel() // Cancel context if no active node found
		return nil, fmt.Errorf("no enabled nodes provided for pipeline %s", pipelineID)
	}

	log.Printf("NewManagedPipeline [%s]: Initializing with active node %s (WSS: %s, HTTP: %s)",
		pipelineID, activeNode.Name, activeNode.WssURL, activeNode.HttpURL)

	// Initialize Source Adapter
	sourceAdapter := NewWebSocketSourceAdapter(activeNode.WssURL, activeNode.HttpURL)

	// NATS publishing will be handled directly in the Run method using mp.natsConn.
	// Stream/Subject determination will also be part of the Run/publish logic.
	log.Printf("ManagedPipeline [%s]: NATS connection available for direct publishing.", pipelineID)

	return &ManagedPipeline{
		id:               pipelineID,
		network:          network,
		subnet:           subnet,
		vmType:           vmType,
		nodeConfigs:      initialNodes,
		activeNodeConfig: activeNode,
		natsConn:         natsConn,
		redisClient:      redisClient,
		statusUpdater:    statusUpdater,
		source:           sourceAdapter,
		ctx:              mpCtx,
		cancel:           mpCancel,
		arrowWriter:      arrowWriter,
	}, nil
}

// ... rest of the code remains the same ...
// UpdateNodeConfigs updates the list of nodes for this pipeline. It re-evaluates the active node
// and reconfigures the underlying source if the active node or its connection details change.
func (mp *ManagedPipeline) UpdateNodeConfigs(newNodes []common.NodeConfig) error {

	log.Printf("ManagedPipeline [%s]: Updating node configurations with %d new nodes.", mp.id, len(newNodes))
	mp.nodeConfigs = newNodes // Store all current nodes for this pipeline

	// Select the new active node from the updated list
	// Strategy: Use the last enabled node (newest) to allow new nodes to become active
	var newPotentialActiveNode common.NodeConfig
	foundEnabledNode := false
	for i := len(newNodes) - 1; i >= 0; i-- {
		node := newNodes[i]
		if node.IsEnabled {
			newPotentialActiveNode = node
			foundEnabledNode = true
			log.Printf("ManagedPipeline [%s]: Selected node %s (%s) as potential active node (newest enabled strategy).", mp.id, node.ID, node.Name)
			break // Using the last enabled node (newest)
		}
	}

	if !foundEnabledNode {
		log.Printf("ManagedPipeline [%s]: No enabled nodes found in the updated list. Pipeline will become inactive.", mp.id)
		if mp.source != nil {
			log.Printf("ManagedPipeline [%s]: Closing source as no active nodes are available.", mp.id)
			if err := mp.source.Close(); err != nil {
				log.Printf("ManagedPipeline [%s]: Error closing source: %v", mp.id, err)
				// Non-fatal for UpdateNodeConfigs itself, but pipeline is now sourceless
			}
		}
		// Update status of the previously active node if it existed
		if mp.activeNodeConfig.ID != "" && mp.statusUpdater != nil {
			go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusStale, "pipeline has no active nodes after update")
		}
		mp.activeNodeConfig = common.NodeConfig{} // Clear current active node
		return fmt.Errorf("no enabled nodes in the updated list for pipeline %s", mp.id)
	}

	// Current active node details before any change
	oldActiveNodeID := mp.activeNodeConfig.ID
	oldActiveNodeName := mp.activeNodeConfig.Name
	oldActiveNodeWssURL := mp.activeNodeConfig.WssURL
	oldActiveNodeHttpURL := mp.activeNodeConfig.HttpURL

	// Check if the active node needs to change or its configuration needs updating
	needsSourceReconfiguration := false
	if mp.activeNodeConfig.ID != newPotentialActiveNode.ID {
		log.Printf("ManagedPipeline [%s]: Active node changing from %s (%s) to %s (%s).",
			mp.id, oldActiveNodeID, oldActiveNodeName, newPotentialActiveNode.ID, newPotentialActiveNode.Name)
		needsSourceReconfiguration = true
	} else if mp.activeNodeConfig.WssURL != newPotentialActiveNode.WssURL || mp.activeNodeConfig.HttpURL != newPotentialActiveNode.HttpURL {
		log.Printf("ManagedPipeline [%s]: Active node %s (%s) connection details changed. WSS: %s->%s, HTTP: %s->%s.",
			mp.id, newPotentialActiveNode.ID, newPotentialActiveNode.Name,
			oldActiveNodeWssURL, newPotentialActiveNode.WssURL,
			oldActiveNodeHttpURL, newPotentialActiveNode.HttpURL)
		needsSourceReconfiguration = true
	}

	if needsSourceReconfiguration {
		mp.activeNodeConfig = newPotentialActiveNode // Update to the new active node (or new version of current)

		if mp.source == nil {
			log.Printf("ManagedPipeline [%s]: Source is nil. Cannot reconfigure. This might be an initialization issue.", mp.id)
			// Attempt to update status for the new active node to Error.
			if mp.statusUpdater != nil {
				go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusError, "pipeline source is nil during reconfiguration")
			}
			return fmt.Errorf("source is nil for pipeline %s during node update", mp.id)
		}

		log.Printf("ManagedPipeline [%s]: Reconfiguring source for active node %s (%s).", mp.id, mp.activeNodeConfig.ID, mp.activeNodeConfig.Name)
		if err := mp.source.UpdateEndpoints(mp.activeNodeConfig.WssURL, mp.activeNodeConfig.HttpURL); err != nil {
			log.Printf("ManagedPipeline [%s]: Error updating source endpoints for %s: %v. Pipeline may be unhealthy.", mp.id, mp.activeNodeConfig.Name, err)
			if mp.statusUpdater != nil {
				go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusError, fmt.Sprintf("failed to update source endpoints: %v", err))
				if oldActiveNodeID != "" && oldActiveNodeID != mp.activeNodeConfig.ID { // If there was a different old active node
					go mp.statusUpdater(oldActiveNodeID, common.NodeStatusStale, "switched to new active node which failed endpoint update")
				}
			}
			return fmt.Errorf("failed to update source endpoints for %s: %w", mp.activeNodeConfig.Name, err)
		}

		log.Printf("ManagedPipeline [%s]: Restarting source with new active node %s (%s).", mp.id, mp.activeNodeConfig.ID, mp.activeNodeConfig.Name)
		if err := mp.source.Start(mp.ctx); err != nil { // mp.ctx is the pipeline's operational context
			log.Printf("ManagedPipeline [%s]: Error restarting source for new active node %s: %v. Pipeline may be unhealthy.", mp.id, mp.activeNodeConfig.Name, err)
			if mp.statusUpdater != nil {
				go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusError, fmt.Sprintf("failed to restart source: %v", err))
				if oldActiveNodeID != "" && oldActiveNodeID != mp.activeNodeConfig.ID {
					go mp.statusUpdater(oldActiveNodeID, common.NodeStatusStale, "switched to new active node which failed source restart")
				}
			}
			return fmt.Errorf("failed to restart source for %s: %w", mp.activeNodeConfig.Name, err)
		}

		log.Printf("ManagedPipeline [%s]: Source reconfigured and restarted successfully with active node %s (%s).", mp.id, mp.activeNodeConfig.ID, mp.activeNodeConfig.Name)
		if mp.statusUpdater != nil {
			go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusActive, "") // New/updated active node is now Active
			if oldActiveNodeID != "" && oldActiveNodeID != mp.activeNodeConfig.ID {  // If there was a different old active node
				go mp.statusUpdater(oldActiveNodeID, common.NodeStatusStale, "no longer the active node for this pipeline")
			}
		}
	} else {
		log.Printf("ManagedPipeline [%s]: Active node %s (%s) and its configuration remain unchanged. No source reconfiguration needed.",
			mp.id, mp.activeNodeConfig.ID, mp.activeNodeConfig.Name)
	}

	return nil
}

// Run starts the managed pipeline's operations. It starts its configured HeadSource,
// listens for new block head events, and publishes them to a NATS subject.
func (mp *ManagedPipeline) Run() error {
	mp.wg.Add(1)
	defer mp.wg.Done()

	// Check if already running
	if mp.ctx != nil {
		return fmt.Errorf("ManagedPipeline [%s]: already running", mp.id)
	}

	// Create a context that will control the lifecycle of this pipeline
	mp.ctx, mp.cancel = context.WithCancel(context.Background())

	log.Printf("ManagedPipeline [%s]: Starting Run loop for active node %s (%s)", mp.id, mp.activeNodeConfig.ID, mp.activeNodeConfig.Name)

	if mp.source == nil {
		log.Printf("ManagedPipeline [%s]: Source is nil. Cannot start Run loop.", mp.id)
		if mp.statusUpdater != nil {
			go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusError, "pipeline source is nil at Run start")
		}
		return fmt.Errorf("source is nil for pipeline %s at Run start", mp.id)
	}

	// Start the source
	if err := mp.source.Start(mp.ctx); err != nil {
		log.Printf("ManagedPipeline [%s]: Failed to start source: %v", mp.id, err)
		return fmt.Errorf("failed to start source: %w", err)
	}

	// Start the ArrowWriter for transaction persistence
	log.Printf("ManagedPipeline [%s]: Starting ArrowWriter for transaction persistence", mp.id)
	mp.wg.Add(1)
	go func() {
		defer mp.wg.Done()
		if err := mp.arrowWriter.Start(mp.ctx); err != nil && err != context.Canceled {
			log.Printf("ManagedPipeline [%s]: ArrowWriter stopped with error: %v", mp.id, err)
			// Update node status if there's an error with the ArrowWriter
			if mp.statusUpdater != nil {
				mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusUnhealthy,
					fmt.Sprintf("ArrowWriter failed: %v", err))
			}
		} else {
			log.Printf("ManagedPipeline [%s]: ArrowWriter stopped gracefully", mp.id)
		}
	}()

	log.Printf("ManagedPipeline [%s]: Source started successfully for node %s.", mp.id, mp.activeNodeConfig.Name)
	if mp.statusUpdater != nil {
		// Update status to Active once source has successfully started
		go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusActive, "")
	}

	for {
		select {
		case <-mp.ctx.Done():
			log.Printf("ManagedPipeline [%s]: Context cancelled. Shutting down Run loop for node %s.", mp.id, mp.activeNodeConfig.Name)
			if mp.source != nil {
				if err := mp.source.Close(); err != nil {
					log.Printf("ManagedPipeline [%s]: Error closing source during shutdown: %v", mp.id, err)
				}
			}
			// Update status to Stale on graceful shutdown if it was previously Active
			// This assumes the supervisor will handle removing it or marking it differently if the whole pipeline is stopping.
			if mp.statusUpdater != nil && mp.activeNodeConfig.ID != "" {
				// Check current status before marking stale, could be Error already
				// For simplicity now, just mark Stale if context is done.
				go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusStale, "pipeline run loop shut down")
			}
			return mp.ctx.Err()

		case headData, ok := <-mp.source.Out():
			if !ok {
				log.Printf("ManagedPipeline [%s]: Source channel closed for node %s. Assuming graceful shutdown or error.", mp.id, mp.activeNodeConfig.Name)
				// If source channel closes unexpectedly, it might indicate an error with the source.
				if mp.statusUpdater != nil {
					go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusUnhealthy, "source channel closed unexpectedly")
				}
				return fmt.Errorf("source channel closed for pipeline %s", mp.id) // Treat as an error for the Run loop
			}

			newHead, ok := headData.(*common.NewHeadEvent)
			if !ok {
				log.Printf("ManagedPipeline [%s]: Received unexpected data type from source: %T for node %s", mp.id, headData, mp.activeNodeConfig.Name)
				if mp.statusUpdater != nil {
					go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusUnhealthy, "unexpected data type from source")
				}
				continue
			}

			// Populate NodeID if it's empty (which it will be from WebSocketSource as it doesn't know our specific node ID)
			if newHead.NodeID == "" && mp.activeNodeConfig.ID != "" {
				newHead.NodeID = mp.activeNodeConfig.ID
				log.Printf("ManagedPipeline [%s]: Populated NodeID %s into NewHeadEvent from active config for node %s", mp.id, newHead.NodeID, mp.activeNodeConfig.Name)
			} else if newHead.NodeID == "" && mp.activeNodeConfig.ID == "" {
				log.Printf("ManagedPipeline [%s]: Warning - NewHeadEvent NodeID is empty and activeNodeConfig.ID is also empty. Cannot reliably set NodeID.", mp.id)
				// Potentially skip publishing or use a default if this case is problematic
			}

			log.Printf("ManagedPipeline [%s]: Received NewHeadEvent from node %s (Event NodeID: %s): Hash %s, Number %d",
				mp.id, mp.activeNodeConfig.Name, newHead.NodeID, newHead.Hash, newHead.Number)

			payload, err := json.Marshal(newHead) // Marshal the received NewHeadEvent
			if err != nil {
				log.Printf("ManagedPipeline [%s]: Error marshalling NewHeadEvent for node %s (Event NodeID: %s): %v", mp.id, mp.activeNodeConfig.Name, newHead.NodeID, err)
				if mp.statusUpdater != nil {
					// Use newHead.NodeID if available and appropriate for status update, otherwise activeNodeConfig.ID
					statusNodeID := mp.activeNodeConfig.ID
					if newHead.NodeID != "" {
						statusNodeID = newHead.NodeID
					}
					go mp.statusUpdater(statusNodeID, common.NodeStatusUnhealthy, fmt.Sprintf("failed to marshal NewHeadEvent: %v", err))
				}
				continue // Don't stop the pipeline for a single marshalling error
			}

			// Construct NATS subject: <network>.<subnet>.<vmType>.newheads
			natsSubject := fmt.Sprintf("%s.%s.%s.newheads",
				strings.ToLower(mp.network),
				strings.ToLower(mp.subnet),
				strings.ToLower(mp.vmType))

			if err := mp.natsConn.Publish(natsSubject, payload); err != nil {
				log.Printf("ManagedPipeline [%s]: Error publishing head data to NATS subject %s for node %s: %v", mp.id, natsSubject, mp.activeNodeConfig.Name, err)
				if mp.statusUpdater != nil {
					// This could be a transient NATS issue or a more persistent one.
					// Marking as Unhealthy allows for recovery attempts or supervisor intervention.
					go mp.statusUpdater(mp.activeNodeConfig.ID, common.NodeStatusUnhealthy, fmt.Sprintf("failed to publish to NATS: %v", err))
				}
				// Depending on policy, might continue or break/return error.
				// For now, continue, assuming it might be a transient NATS issue.
				continue
			}
			log.Printf("ManagedPipeline [%s]: Published head data to NATS subject %s for node %s.", mp.id, natsSubject, mp.activeNodeConfig.Name)
		}
	}
}

// Stop signals the ManagedPipeline to shut down gracefully by cancelling its context.
// This will also stop the ArrowWriter via the context cancellation.
func (mp *ManagedPipeline) Stop() {
	log.Printf("ManagedPipeline [%s]: Signaling stop...", mp.id)
	if mp.cancel != nil {
		mp.cancel() // Trigger context cancellation. Run() loop will handle source.Close() and ArrowWriter shutdown.
	}
}

// Stop signals the ManagedPipeline to shut down gracefully by cancelling its context.
// This will also stop the ArrowWriter via the context cancellation.

// Wait blocks until the ManagedPipeline's Run method has completed and all associated goroutines are done.
func (mp *ManagedPipeline) Wait() {
	log.Printf("ManagedPipeline [%s]: Waiting for pipeline to complete...", mp.id)
	mp.wg.Wait()
	log.Printf("ManagedPipeline [%s]: Pipeline completed.", mp.id)
}

// TODO: Adapt blockchain.WebSocketSource to implement HeadSource interface (if not already done by WebSocketSourceAdapter's methods)

// Helper functions for environment variable parsing

// getEnvWithDefault gets an environment variable or returns a default value if not found
func getEnvWithDefault(key, defaultValue string) string {
	value, exists := os.LookupEnv(key)
	if !exists {
		return defaultValue
	}
	return value
}

// getEnvBoolWithDefault gets a boolean environment variable or returns a default value if not found
func getEnvBoolWithDefault(key string, defaultValue bool) bool {
	value, exists := os.LookupEnv(key)
	if !exists {
		return defaultValue
	}

	boolValue, err := strconv.ParseBool(value)
	if err != nil {
		return defaultValue
	}

	return boolValue
}
