package testutils

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/redis/go-redis/v9"
	"github.com/testcontainers/testcontainers-go"
	tcRedis "github.com/testcontainers/testcontainers-go/modules/redis"
	"github.com/testcontainers/testcontainers-go/wait"

	"github.com/web3ekko/ekko-ce/pipeline/pkg/decoder"
)

var (
	once sync.Once

	// Shared clients
	redisClient *redis.Client
	natsConn    *nats.Conn
	jetStream   nats.JetStreamContext

	// Container references (for cleanup)
	redisContainer testcontainers.Container
	natsContainer  testcontainers.Container

	// Cleanup function
	globalCleanup func()
)

// GetTestEnvironment returns shared Redis and NATS instances
func GetTestEnvironment(ctx context.Context) (decoder.RedisClient, *nats.Conn, nats.JetStreamContext, error) {
	var initErr error

	once.Do(func() {
		redisClient, natsConn, jetStream, initErr = setupGlobalTestEnvironment(ctx)
	})

	if initErr != nil {
		return nil, nil, nil, fmt.Errorf("failed to initialize test environment: %w", initErr)
	}

	// Reset data between tests
	err := redisClient.FlushAll(ctx).Err()
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to flush Redis: %w", err)
	}

	return redisClient, natsConn, jetStream, nil
}

// CleanupTestEnvironment should be called from TestMain after all tests
func CleanupTestEnvironment() {
	if globalCleanup != nil {
		globalCleanup()
	}
}

// setupGlobalTestEnvironment initializes containers once
func setupGlobalTestEnvironment(ctx context.Context) (*redis.Client, *nats.Conn, nats.JetStreamContext, error) {
	// Start Redis container
	redisC, err := tcRedis.RunContainer(ctx, testcontainers.WithImage("redis:7"))
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to start Redis: %w", err)
	}
	redisContainer = redisC

	// Get Redis connection details
	redisHost, err := redisC.Host(ctx)
	if err != nil {
		return nil, nil, nil, err
	}
	redisPort, err := redisC.MappedPort(ctx, "6379/tcp")
	if err != nil {
		return nil, nil, nil, err
	}
	redisAddr := fmt.Sprintf("%s:%s", redisHost, redisPort.Port())

	// Connect to Redis
	redisClientOpts := &redis.Options{Addr: redisAddr}
	rc := redis.NewClient(redisClientOpts)
	
	// Test Redis connection
	_, err = rc.Ping(ctx).Result()
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to ping Redis: %w", err)
	}

	// Start NATS container with tmpfs
	natsReq := testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image:        "nats:2.10-alpine",
			ExposedPorts: []string{"4222/tcp"},
			Cmd:          []string{"-js", "-sd", "/data/jetstream"},
			Tmpfs:        map[string]string{"/data/jetstream": "rw"}, // Using tmpfs as preferred
			WaitingFor:   wait.ForLog("Listening for client connections").WithStartupTimeout(10 * time.Second),
		},
		Started: true,
	}

	natsC, err := testcontainers.GenericContainer(ctx, natsReq)
	if err != nil {
		redisC.Terminate(ctx)
		return nil, nil, nil, fmt.Errorf("failed to start NATS: %w", err)
	}
	natsContainer = natsC

	// Get NATS connection details
	natsHost, err := natsC.Host(ctx)
	if err != nil {
		return nil, nil, nil, err
	}
	natsPort, err := natsC.MappedPort(ctx, "4222/tcp")
	if err != nil {
		return nil, nil, nil, err
	}
	natsURL := fmt.Sprintf("nats://%s:%s", natsHost, natsPort.Port())

	// Connect to NATS
	nc, err := nats.Connect(natsURL)
	if err != nil {
		return nil, nil, nil, err
	}

	// Get JetStream context
	js, err := nc.JetStream()
	if err != nil {
		nc.Close()
		return nil, nil, nil, err
	}

	// Setup cleanup function
	globalCleanup = func() {
		ctx := context.Background()
		if nc != nil {
			nc.Close()
		}
		if rc != nil {
			rc.Close()
		}
		if natsC != nil {
			_ = natsC.Terminate(ctx)
		}
		if redisC != nil {
			_ = redisC.Terminate(ctx)
		}
	}

	return rc, nc, js, nil
}

// GetTestKeyValueStore creates a fresh KeyValue store for a test
func GetTestKeyValueStore(js nats.JetStreamContext, testName string) (nats.KeyValue, error) {
	// Sanitize test name for use as bucket name
	bucketName := fmt.Sprintf("test_kv_%s", testName)
	
	// NATS has limits on bucket name length and format
	if len(bucketName) > 64 {
		bucketName = bucketName[:64]
	}

	kvConfig := nats.KeyValueConfig{
		Bucket: bucketName,
	}

	kv, err := js.CreateKeyValue(&kvConfig)
	if err != nil {
		if err == nats.ErrStreamNameAlreadyInUse {
			// If it exists, try to use it
			kv, err = js.KeyValue(kvConfig.Bucket)
			if err != nil {
				return nil, err
			}
			// Delete all keys to start fresh
			keys, _ := kv.Keys()
			for _, k := range keys {
				_ = kv.Delete(k)
			}
			return kv, nil
		}
		return nil, err
	}

	return kv, nil
}
