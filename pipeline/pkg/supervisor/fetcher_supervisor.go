package supervisor

import (
	"context"
	"fmt"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
	ekkoCommon "github.com/web3ekko/ekko-ce/pipeline/pkg/common"
	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder" // For RedisClient type
	"github.com/web3ekko/ekko-ce/pipeline/pkg/fetchers"
)

const (
	defaultFetcherSupervisorSyncInterval = 15 * time.Second
)

// FetcherConfig represents the information needed to run a BlockFetcher.
// For now, the presence of a key in the KV store is enough, but we can expand this.
// The key itself will be structured e.g., fetcher.config.<network>.<subnet>.<vmType>
type FetcherConfig struct {
	Network string `json:"network"`
	Subnet  string `json:"subnet"`
	VMType  string `json:"vmType"`
	// Add other specific configurations if a fetcher needs more than just these identifiers
}

// FetcherSupervisor manages the lifecycle of BlockFetcher instances.
type FetcherSupervisor struct {
	ctx      context.Context
	cancel   context.CancelFunc
	natsConn *nats.Conn
	jsCtx    nats.JetStreamContext
	// fetcherConfigKV is removed as configs are now derived from allNodeConfigs
	fetcherDataKVName    string // Name of the KV store to be used by individual fetchers for their data
	redisClient          decoder.RedisClient
	allNodeConfigs       []ekkoCommon.NodeConfig // All node configurations provided by PipelineSupervisor
	filterWalletsEnabled bool                    // New: To store the FILTER_WALLETS setting

	activeFetchers map[string]*managedFetcher // Map key: "<nodeID>"
	mu             sync.Mutex
	wg             sync.WaitGroup
}

// managedFetcher wraps a BlockFetcher with its own context for lifecycle management.
type managedFetcher struct {
	instance *fetchers.BlockFetcher
	config   FetcherConfig
	ctx      context.Context
	cancel   context.CancelFunc
	wg       sync.WaitGroup
}

// NewFetcherSupervisor creates a new FetcherSupervisor.
// fetcherConfigKVName is the name of the NATS KV bucket to watch for fetcher configurations.
// fetcherDataKVName is the name of the NATS KV bucket that fetchers will use for their operational data.
func NewFetcherSupervisor(
	appCtx context.Context,
	nc *nats.Conn,
	// fetcherConfigKVName string, // Removed, no longer watching a dedicated KV for configs
	fetcherDataKVName string,
	redisClient decoder.RedisClient,
	nodeCfgs []ekkoCommon.NodeConfig,
) (*FetcherSupervisor, error) {
	if nc == nil {
		return nil, fmt.Errorf("NATS connection cannot be nil")
	}
	// fetcherConfigKVName check removed
	if fetcherDataKVName == "" {
		return nil, fmt.Errorf("fetcherDataKVName cannot be empty")
	}

	js, err := nc.JetStream()
	if err != nil {
		return nil, fmt.Errorf("failed to get JetStream context: %w", err)
	}

	// fetcherConfigKV logic removed

	// Note: We don't create/get the fetcherDataKV here, as each BlockFetcher might use it differently
	// or it might be pre-configured. The supervisor just passes the name along.

	supervisorCtx, supervisorCancel := context.WithCancel(appCtx)

	// Read FILTER_WALLETS environment variable
	filterWalletsEnv := strings.ToLower(os.Getenv("FILTER_WALLETS"))
	filterWalletsEnabled := true // Default to true
	if filterWalletsEnv == "false" {
		filterWalletsEnabled = false
	}
	log.Printf("FetcherSupervisor: Wallet filtering is %s (FILTER_WALLETS=%s)", map[bool]string{true: "ENABLED", false: "DISABLED"}[filterWalletsEnabled], os.Getenv("FILTER_WALLETS"))

	// Make a copy of nodeCfgs to avoid external modification issues if the slice is reused by the caller.
	initialNodeConfigs := make([]ekkoCommon.NodeConfig, len(nodeCfgs))
	copy(initialNodeConfigs, nodeCfgs)

	fs := &FetcherSupervisor{
		ctx:      supervisorCtx,
		cancel:   supervisorCancel,
		natsConn: nc,
		jsCtx:    js,
		// fetcherConfigKV: configKV, // Removed
		fetcherDataKVName:    fetcherDataKVName,
		redisClient:          redisClient,
		allNodeConfigs:       initialNodeConfigs,   // Store initial nodeCfgs
		filterWalletsEnabled: filterWalletsEnabled, // New
		activeFetchers:       make(map[string]*managedFetcher),
	}

	return fs, nil
}

// Run starts the FetcherSupervisor's operations.
func (fs *FetcherSupervisor) Run() error {
	fs.wg.Add(1)
	defer fs.wg.Done()

	log.Printf("FetcherSupervisor: Starting...")

	// Initial synchronization
	if err := fs.synchronizeFetchers(); err != nil {
		log.Printf("FetcherSupervisor: Error during initial synchronization: %v", err)
		// Depending on severity, might return err or just log
	}

	// KV watcher logic removed as configurations are now driven by allNodeConfigs and UpdateNodeConfigs method.

	// Periodic synchronization ticker
	ticker := time.NewTicker(defaultFetcherSupervisorSyncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-fs.ctx.Done():
			log.Printf("FetcherSupervisor: Context cancelled. Shutting down.")
			fs.shutdownAllFetchers()
			return nil
		case <-ticker.C:
			log.Printf("FetcherSupervisor: Periodic sync triggered.")
			if err := fs.synchronizeFetchers(); err != nil {
				log.Printf("FetcherSupervisor: Error during periodic synchronization: %v", err)
			}
		}
	}
}

// UpdateNodeConfigs is called by the PipelineSupervisor when the list of available/active
// node configurations changes. It updates the internal list and triggers a synchronization.
func (fs *FetcherSupervisor) UpdateNodeConfigs(newConfigs []ekkoCommon.NodeConfig) {
	log.Printf("FetcherSupervisor: Received updated node configurations. Count: %d. Triggering sync.", len(newConfigs))

	fs.mu.Lock()
	fs.allNodeConfigs = make([]ekkoCommon.NodeConfig, len(newConfigs)) // Create a new slice
	copy(fs.allNodeConfigs, newConfigs)                                // Copy contents
	fs.mu.Unlock()

	// Trigger synchronization in a goroutine to avoid blocking the caller (PipelineSupervisor).
	go func() {
		// Add a small delay to allow NATS propagation if this call is too quick after a KV update
		// time.Sleep(500 * time.Millisecond) // Optional: consider if needed for KV propagation race conditions
		if err := fs.synchronizeFetchers(); err != nil {
			log.Printf("FetcherSupervisor: Error during synchronization triggered by UpdateNodeConfigs: %v", err)
		}
	}()
}

// synchronizeFetchers reconciles the active fetchers based on the current allNodeConfigs.
func (fs *FetcherSupervisor) synchronizeFetchers() error {
	fs.mu.Lock()
	defer fs.mu.Unlock()

	log.Printf("FetcherSupervisor: Starting fetcher synchronization based on %d node configurations...", len(fs.allNodeConfigs))

	desiredFetchers := make(map[string]ekkoCommon.NodeConfig) // Key: <nodeID>

	for _, nodeCfg := range fs.allNodeConfigs {
		if !nodeCfg.IsEnabled {
			continue // Only consider enabled nodes for fetchers
		}

		fetcherKey := nodeCfg.ID // Use node ID as the unique key

		desiredFetchers[fetcherKey] = nodeCfg
		log.Printf("FetcherSupervisor: Identified desired fetcher for node: ID=%s, Name=%s, Network=%s, Subnet=%s, VMType=%s", fetcherKey, nodeCfg.Name, nodeCfg.Network, nodeCfg.Subnet, nodeCfg.VMType)
	}

	// Stop fetchers that are running but no longer desired
	for key, mf := range fs.activeFetchers {
		if _, exists := desiredFetchers[key]; !exists {
			log.Printf("FetcherSupervisor: Stopping fetcher for %s as no enabled node configuration matches this type.", key)
			fs.stopFetcherLocked(key, mf) // Call internal locked version
		}
	}

	// Start fetchers that are desired but not yet running
	for fetcherKey, nodeConfig := range desiredFetchers { // fetcherKey is nodeID, nodeConfig is the NodeConfig
		if _, exists := fs.activeFetchers[fetcherKey]; !exists {
			log.Printf("FetcherSupervisor: Starting new fetcher for node %s (%s) - Network: %s, Subnet: %s, VMType: %s", nodeConfig.Name, nodeConfig.ID, nodeConfig.Network, nodeConfig.Subnet, nodeConfig.VMType)
			fs.startFetcherLocked(fetcherKey, nodeConfig) // Pass nodeID and NodeConfig directly
		}
	}

	log.Printf("FetcherSupervisor: Fetcher synchronization complete. %d fetchers active.", len(fs.activeFetchers))
	return nil
}

// startFetcherLocked starts a new BlockFetcher instance. Assumes fs.mu is held.
// key is the node identifier (nodeID).
// nodeForFetcher is the specific NodeConfig that will be used to instantiate the BlockFetcher.
func (fs *FetcherSupervisor) startFetcherLocked(key string, nodeForFetcher ekkoCommon.NodeConfig) {
	// Ensure data KV store for the fetcher
	// It's assumed that the fetcherDataKVName refers to a single KV store shared by all fetchers,
	// or that BlockFetcher internally handles namespacing if needed.
	dataKVForFetcher, err := fs.jsCtx.KeyValue(fs.fetcherDataKVName)
	if err != nil {
		log.Printf("FetcherSupervisor: Fetcher data KV store '%s' not found for fetcher '%s', attempting to create...", fs.fetcherDataKVName, key)
		dataKVForFetcher, err = fs.jsCtx.CreateKeyValue(&nats.KeyValueConfig{
			Bucket: fs.fetcherDataKVName,
		})
		if err != nil {
			log.Printf("FetcherSupervisor: Failed to create/get data KV store '%s' for fetcher '%s': %v. Skipping fetcher.", fs.fetcherDataKVName, key, err)
			return
		}
	}

	bf, err := fetchers.NewBlockFetcher(nodeForFetcher, fs.natsConn, dataKVForFetcher, fs.redisClient, fs.filterWalletsEnabled)
	if err != nil {
		log.Printf("FetcherSupervisor: Error creating BlockFetcher for %s (Node: %s): %v", key, nodeForFetcher.ID, err)
		return
	}

	mfCtx, mfCancel := context.WithCancel(fs.ctx) // Child context from supervisor's context
	mf := &managedFetcher{
		instance: bf,
		config:   fetcherDetails,
		ctx:      mfCtx,
		cancel:   mfCancel,
	}

	fs.activeFetchers[key] = mf // Add to active map under lock

	mf.wg.Add(1) // For this specific fetcher's goroutine
	fs.wg.Add(1) // For the supervisor to wait on this fetcher's goroutine as a whole

	go func(managedF *managedFetcher, cKey string, nodeID string) {
		defer managedF.wg.Done() // Signal this fetcher's goroutine completion
		defer fs.wg.Done()       // Signal to supervisor that one of its main tasks is done

		log.Printf("FetcherSupervisor: Goroutine starting for BlockFetcher %s (Node: %s)", cKey, nodeID)
		runErr := managedF.instance.Run(managedF.ctx) // This blocks until the fetcher stops or context is cancelled

		if runErr != nil {
			log.Printf("FetcherSupervisor: BlockFetcher %s (Node: %s) Run loop exited with error: %v", cKey, nodeID, runErr)
		} else {
			log.Printf("FetcherSupervisor: BlockFetcher %s (Node: %s) Run loop finished gracefully.", cKey, nodeID)
		}

		// Post-run cleanup, executed after the fetcher's Run() method returns.
		// This section handles removal from activeFetchers if the fetcher stopped on its own
		// (i.e., not due to a direct call to stopFetcherLocked or shutdownAllFetchers).
		fs.mu.Lock()
		// Check if the supervisor itself is not shutting down (fs.ctx.Err() == nil)
		// AND if this specific fetcher's context was not cancelled by stopFetcherLocked/shutdownAllFetchers (managedF.ctx.Err() == nil).
		// If both are true, it means the fetcher stopped for other reasons (e.g. completed its task, or an internal unrecoverable error).
		if fs.ctx.Err() == nil && managedF.ctx.Err() == nil {
			// Double-check it's still in activeFetchers, as stopFetcherLocked might have been called concurrently
			if activeInstance, stillActive := fs.activeFetchers[cKey]; stillActive && activeInstance == managedF {
				log.Printf("FetcherSupervisor: BlockFetcher %s (Node: %s) stopped independently. Removing from active list.", cKey, nodeID)
				delete(fs.activeFetchers, cKey)
			}
		} else if managedF.ctx.Err() != nil {
			// If managedF.ctx.Err() is not nil, it means stopFetcherLocked or shutdownAllFetchers was called.
			// stopFetcherLocked already removes it from activeFetchers. shutdownAllFetchers clears the map.
			// So, no explicit delete(fs.activeFetchers, cKey) is needed here for that case.
			log.Printf("FetcherSupervisor: BlockFetcher %s (Node: %s) was stopped by supervisor directive.", cKey, nodeID)
		}
		fs.mu.Unlock()

	}(mf, key, nodeForFetcher.ID) // Pass necessary identifiers to the goroutine

	log.Printf("FetcherSupervisor: BlockFetcher for %s (Node: %s) has been started and goroutine launched.", key, nodeForFetcher.ID)
}

// stopFetcherLocked stops a managed fetcher. Assumes fs.mu is held.
// This function is responsible for initiating the stop and removing from activeFetchers.
// The goroutine in startFetcherLocked handles wg.Done() and potential self-removal if it stops for other reasons.
func (fs *FetcherSupervisor) stopFetcherLocked(key string, mf *managedFetcher) {
	if mf == nil {
		log.Printf("FetcherSupervisor: stopFetcherLocked called for key %s with nil managedFetcher.", key)
		return
	}
	log.Printf("FetcherSupervisor: Stopping BlockFetcher for %s (Node: %s)...", key, mf.instance.NodeConfig().ID)

	delete(fs.activeFetchers, key) // Remove from active list immediately under lock
	log.Printf("FetcherSupervisor: Removed %s from active fetchers map.", key)

	mf.cancel() // Signal the fetcher's context to cancel. Its goroutine will handle wg.Done().
	// DO NOT call mf.wg.Wait() here as fs.mu is held, could lead to deadlock if the fetcher's goroutine
	// tries to acquire fs.mu (e.g., in its cleanup logic, though current design avoids this).
	// The supervisor's main fs.wg.Wait() in its Stop() method will eventually wait for all fetcher goroutines.
}

// shutdownAllFetchers signals all active fetchers to stop and waits for them.
func (fs *FetcherSupervisor) shutdownAllFetchers() {
	fs.mu.Lock()
	log.Printf("FetcherSupervisor: Shutting down all %d active fetchers...", len(fs.activeFetchers))
	activeFetchersToShutdown := make([]*managedFetcher, 0, len(fs.activeFetchers))

	// First, signal all fetchers to stop and collect them
	for key, mf := range fs.activeFetchers {
		log.Printf("FetcherSupervisor: Signaling shutdown for fetcher %s (Node: %s)", key, mf.instance.NodeConfig().ID)
		mf.cancel() // Signal stop
		activeFetchersToShutdown = append(activeFetchersToShutdown, mf)
	}
	fs.activeFetchers = make(map[string]*managedFetcher) // Clear the map of active fetchers immediately
	fs.mu.Unlock()                                       // Release lock before waiting

	// Wait for all fetchers to complete their shutdown outside the lock
	log.Printf("FetcherSupervisor: Waiting for %d fetchers to confirm shutdown...", len(activeFetchersToShutdown))
	for _, mf := range activeFetchersToShutdown {
		mf.wg.Wait() // Wait for the fetcher's goroutine to finish
		log.Printf("FetcherSupervisor: Fetcher (Node: %s) confirmed shutdown.", mf.instance.NodeConfig().ID)
	}
	log.Println("FetcherSupervisor: All fetchers have been shut down.")
}

// Stop gracefully shuts down the FetcherSupervisor and all its managed fetchers.
func (fs *FetcherSupervisor) Stop() {
	log.Printf("FetcherSupervisor: Stop called. Initiating shutdown...")
	// Signal the main Run loop and KV watcher to stop
	fs.cancel()

	// Wait for all goroutines (main loop, watcher, fetchers) to complete.
	fs.Wait()
	log.Printf("FetcherSupervisor: Shutdown complete.")
}

// Wait blocks until all goroutines started by the FetcherSupervisor have completed.
func (fs *FetcherSupervisor) Wait() {
	fs.wg.Wait()
}
