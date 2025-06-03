package supervisor

import (
	"context"
	"fmt"
	"log"
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
	fetcherConfigKVPrefix              = "fetcher.config." // Prefix for keys in the config KV store
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
	ctx                 context.Context
	cancel              context.CancelFunc
	natsConn            *nats.Conn
	jsCtx               nats.JetStreamContext
	fetcherConfigKV     nats.KeyValue // KV store for fetcher configurations
	fetcherDataKVName   string        // Name of the KV store to be used by individual fetchers for their data
	redisClient         decoder.RedisClient
	relevantNodeConfigs []ekkoCommon.NodeConfig // All node configurations relevant to this pipeline instance

	activeFetchers map[string]*managedFetcher // Map key: "<network>.<subnet>.<vmType>"
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
	fetcherConfigKVName string,
	fetcherDataKVName string,
	redisClient decoder.RedisClient,
	nodeCfgs []ekkoCommon.NodeConfig, // Added nodeCfgs parameter
) (*FetcherSupervisor, error) {
	if nc == nil {
		return nil, fmt.Errorf("NATS connection cannot be nil")
	}
	if fetcherConfigKVName == "" {
		return nil, fmt.Errorf("fetcherConfigKVName cannot be empty")
	}
	if fetcherDataKVName == "" {
		return nil, fmt.Errorf("fetcherDataKVName cannot be empty")
	}

	js, err := nc.JetStream()
	if err != nil {
		return nil, fmt.Errorf("failed to get JetStream context: %w", err)
	}

	// Get or create the KV store for fetcher configurations
	configKV, err := js.KeyValue(fetcherConfigKVName)
	if err != nil {
		log.Printf("FetcherSupervisor: Fetcher config KV store '%s' not found, attempting to create...", fetcherConfigKVName)
		configKV, err = js.CreateKeyValue(&nats.KeyValueConfig{
			Bucket: fetcherConfigKVName,
			// Add other KV config like TTL, replicas if needed
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create fetcher config KV store '%s': %w", fetcherConfigKVName, err)
		}
		log.Printf("FetcherSupervisor: Created fetcher config KV store '%s'", fetcherConfigKVName)
	}

	// Note: We don't create/get the fetcherDataKV here, as each BlockFetcher might use it differently
	// or it might be pre-configured. The supervisor just passes the name along.
	// Alternatively, the supervisor could ensure this KV store exists too. For now, just passing the name.

	supervisorCtx, supervisorCancel := context.WithCancel(appCtx)

	fs := &FetcherSupervisor{
		ctx:               supervisorCtx,
		cancel:            supervisorCancel,
		natsConn:          nc,
		jsCtx:             js,
		fetcherConfigKV:   configKV,
		fetcherDataKVName: fetcherDataKVName,
		redisClient:         redisClient,
		relevantNodeConfigs: nodeCfgs, // Store nodeCfgs
		activeFetchers:      make(map[string]*managedFetcher),
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

	// Watch for changes in the fetcher configuration KV store
	watchCtx, watchCancel := context.WithCancel(fs.ctx)
	defer watchCancel()

	watcher, err := fs.fetcherConfigKV.WatchAll(nats.Context(watchCtx))
	if err != nil {
		log.Printf("FetcherSupervisor: Error creating KV watcher: %v. Will rely on periodic sync only.", err)
		// If watcher fails, we can fall back to periodic sync only
	} else {
		log.Printf("FetcherSupervisor: Watching KV store '%s' for configuration changes.", fs.fetcherConfigKV.Bucket())
		fs.wg.Add(1)
		go func() {
			defer fs.wg.Done()
			defer log.Printf("FetcherSupervisor: KV watcher stopped.")
			for {
				select {
				case <-fs.ctx.Done(): // Supervisor context cancelled
					watchCancel() // Ensure watcher context is also cancelled
					return
				case entry, ok := <-watcher.Updates():
					if !ok { // Channel closed
						log.Printf("FetcherSupervisor: KV watcher updates channel closed.")
						return
					}
					if entry == nil { // Initial marker or keep-alive
						continue
					}
					log.Printf("FetcherSupervisor: Detected change in KV store for key '%s' (operation: %s). Triggering sync.", entry.Key(), entry.Operation().String())
					if err := fs.synchronizeFetchers(); err != nil {
						log.Printf("FetcherSupervisor: Error during event-driven synchronization: %v", err)
					}
				}
			}
		}()
	}

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

// synchronizeFetchers reconciles the active fetchers with the configurations in the KV store.
func (fs *FetcherSupervisor) synchronizeFetchers() error {
	fs.mu.Lock()
	defer fs.mu.Unlock()

	log.Printf("FetcherSupervisor: Starting fetcher synchronization...")

	desiredConfigs := make(map[string]FetcherConfig)
	keys, err := fs.fetcherConfigKV.Keys()
	if err != nil {
		return fmt.Errorf("failed to list keys from fetcherConfigKV: %w", err)
	}

	for _, key := range keys {
		if !strings.HasPrefix(key, fetcherConfigKVPrefix) {
			continue // Not a fetcher config key
		}
		// Key format: fetcher.config.<network>.<subnet>.<vmType>
		parts := strings.Split(strings.TrimPrefix(key, fetcherConfigKVPrefix), ".")
		if len(parts) != 3 {
			log.Printf("FetcherSupervisor: Invalid key format '%s'. Expected 3 parts after prefix, got %d.", key, len(parts))
			continue
		}
		configKey := fmt.Sprintf("%s.%s.%s", parts[0], parts[1], parts[2]) // <network>.<subnet>.<vmType>
		desiredConfigs[configKey] = FetcherConfig{
			Network: parts[0],
			Subnet:  parts[1],
			VMType:  parts[2],
		}
		// TODO: Potentially read value if config struct becomes more complex: fs.fetcherConfigKV.Get(key)
	}

	log.Printf("FetcherSupervisor: Found %d desired fetcher configurations.", len(desiredConfigs))

	// Start new fetchers or update existing ones (if config content could change)
	for configKey, fetcherTypeCfg := range desiredConfigs { // Renamed config to fetcherTypeCfg for clarity
		if _, exists := fs.activeFetchers[configKey]; !exists {
			log.Printf("FetcherSupervisor: Configuration for fetcher type '%s' found. Attempting to start new fetcher.", configKey)

			// Find a suitable, enabled ekkoCommon.NodeConfig from fs.relevantNodeConfigs
			var selectedNodeConfig *ekkoCommon.NodeConfig
			for _, nc := range fs.relevantNodeConfigs { // nc is a copy of ekkoCommon.NodeConfig
				if nc.Network == fetcherTypeCfg.Network &&
					nc.Subnet == fetcherTypeCfg.Subnet &&
					nc.VMType == fetcherTypeCfg.VMType &&
					nc.IsEnabled {
					
					nodeCfgCopy := nc // Make a copy to ensure we have a stable pointer if needed
					selectedNodeConfig = &nodeCfgCopy
					log.Printf("FetcherSupervisor: Found matching NodeConfig ID '%s' (HttpURL: %s) for fetcher type '%s'.", selectedNodeConfig.ID, selectedNodeConfig.HttpURL, configKey)
					break // Use the first matching enabled node
					// TODO: Implement more sophisticated selection logic if multiple nodes match (e.g., based on a primary flag or health status)
				}
			}

			if selectedNodeConfig == nil {
				log.Printf("FetcherSupervisor: No matching and enabled ekkoCommon.NodeConfig found in supervisor's nodeConfigs for fetcher type '%s' (Network: %s, Subnet: %s, VMType: %s). Skipping fetcher creation.", configKey, fetcherTypeCfg.Network, fetcherTypeCfg.Subnet, fetcherTypeCfg.VMType)
				continue
			}

			// Each fetcher needs its own KV store for its operational data.
			dataKVForFetcher, err := fs.jsCtx.KeyValue(fs.fetcherDataKVName)
			if err != nil {
				log.Printf("FetcherSupervisor: Fetcher data KV store '%s' not found for fetcher '%s', attempting to create...", fs.fetcherDataKVName, configKey)
				dataKVForFetcher, err = fs.jsCtx.CreateKeyValue(&nats.KeyValueConfig{
					Bucket: fs.fetcherDataKVName,
				})
				if err != nil {
					log.Printf("FetcherSupervisor: Failed to create/get data KV store '%s' for fetcher '%s': %v. Skipping fetcher.", fs.fetcherDataKVName, configKey, err)
					continue
				}
				log.Printf("FetcherSupervisor: Ensured data KV store '%s' exists for fetcher '%s'.", fs.fetcherDataKVName, configKey)
			}

			// Use the found selectedNodeConfig (which is ekkoCommon.NodeConfig)
			bf, err := fetchers.NewBlockFetcher(*selectedNodeConfig, fs.natsConn, dataKVForFetcher, fs.redisClient)
			if err != nil {
				log.Printf("FetcherSupervisor: Error creating new BlockFetcher for node ID '%s' (type '%s'): %v. Skipping.", selectedNodeConfig.ID, configKey, err)
				continue
			}

			mfCtx, mfCancel := context.WithCancel(fs.ctx)
			managedF := &managedFetcher{
				instance: bf,
				config:   fetcherTypeCfg, // Keep using the simple FetcherConfig for keying in activeFetchers
				ctx:      mfCtx,
				cancel:   mfCancel,
			}
			fs.activeFetchers[configKey] = managedF

			managedF.wg.Add(1)
			fs.wg.Add(1) // Add to supervisor's waitgroup for overall tracking
			go func(mf *managedFetcher, cKey string) {
				defer mf.wg.Done()
				defer fs.wg.Done() // Decrement supervisor's waitgroup when fetcher goroutine exits
				log.Printf("FetcherSupervisor: Starting BlockFetcher instance for '%s'", cKey)
				if err := mf.instance.Run(mf.ctx); err != nil {
					log.Printf("FetcherSupervisor: BlockFetcher for '%s' exited with error: %v", cKey, err)
					// TODO: Implement retry logic or error handling policy
				}
				log.Printf("FetcherSupervisor: BlockFetcher instance for '%s' stopped.", cKey)

				// Clean up if it stopped and wasn't told to by supervisor context cancellation
				fs.mu.Lock()
				if fs.ctx.Err() == nil { // If supervisor is not shutting down
					log.Printf("FetcherSupervisor: BlockFetcher for '%s' stopped unexpectedly. Removing from active list.", cKey)
					delete(fs.activeFetchers, cKey)
				}
				fs.mu.Unlock()
			}(managedF, configKey)
		}
	}

	// Stop fetchers that are no longer in desired config
	for activeKey, mf := range fs.activeFetchers {
		if _, exists := desiredConfigs[activeKey]; !exists {
			log.Printf("FetcherSupervisor: Configuration for '%s' removed. Stopping fetcher.", activeKey)
			mf.cancel()      // Signal the fetcher's Run loop to stop
			mf.wg.Wait()     // Wait for it to clean up
			delete(fs.activeFetchers, activeKey)
			log.Printf("FetcherSupervisor: Fetcher for '%s' stopped and removed.", activeKey)
		}
	}

	log.Printf("FetcherSupervisor: Synchronization complete. Active fetchers: %d", len(fs.activeFetchers))
	return nil
}

// shutdownAllFetchers signals all active fetchers to stop.
// It does not wait for them to finish, as that is handled by fs.wg.
func (fs *FetcherSupervisor) shutdownAllFetchers() {
	fs.mu.Lock()
	defer fs.mu.Unlock()

	count := len(fs.activeFetchers)
	if count == 0 {
		log.Printf("FetcherSupervisor: No active fetchers to shut down.")
		return
	}

	log.Printf("FetcherSupervisor: Signaling %d active fetcher(s) to stop...", count)
	for key, mf := range fs.activeFetchers {
		log.Printf("FetcherSupervisor: Signaling fetcher '%s' to stop...", key)
		mf.cancel() // This will trigger the fetcher's Run loop to exit and its goroutine to call mf.wg.Done()
	}
	log.Printf("FetcherSupervisor: All active fetchers signaled to stop.")
}

// Stop gracefully shuts down the FetcherSupervisor and all its managed fetchers.
func (fs *FetcherSupervisor) Stop() {
	log.Printf("FetcherSupervisor: Stop called. Initiating shutdown...")
	// Signal the main Run loop and KV watcher to stop
	fs.cancel()

	// Signal all individual fetchers to stop. 
	// The Run loop's defer fs.wg.Done() and the fetcher goroutines' defer mf.wg.Done() (which also calls fs.wg.Done())
	// will ensure fs.wg is correctly decremented.
	// fs.shutdownAllFetchers() // This is called from Run loop when context is cancelled.

	// Wait for all goroutines (main loop, watcher, fetchers) to complete.
	fs.Wait()
	log.Printf("FetcherSupervisor: Shutdown complete.")
}

// Wait blocks until the FetcherSupervisor and all its managed services have stopped.
func (fs *FetcherSupervisor) Wait() {
	log.Printf("FetcherSupervisor: Waiting for all services to stop...")
	fs.wg.Wait()
	log.Printf("FetcherSupervisor: All services stopped.")
}
