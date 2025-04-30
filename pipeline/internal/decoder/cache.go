package decoder

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// Cache interface for storing and retrieving values
type Cache interface {
	GetString(ctx context.Context, key string) (string, error)
	SetString(ctx context.Context, key string, value string, expiration time.Duration) error
}

// MemoryCache implements an in-memory cache with TTL
type MemoryCache struct {
	mu    sync.RWMutex
	items map[string]*cacheItem
}

type cacheItem struct {
	value     string
	expiresAt time.Time
}

// NewMemoryCache creates a new in-memory cache
func NewMemoryCache() *MemoryCache {
	return &MemoryCache{
		items: make(map[string]*cacheItem),
	}
}

// GetString retrieves a value from memory cache
func (c *MemoryCache) GetString(ctx context.Context, key string) (string, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	item, exists := c.items[key]
	if !exists || time.Now().After(item.expiresAt) {
		if exists {
			delete(c.items, key)
		}
		return "", fmt.Errorf("key not found: %s", key)
	}

	return item.value, nil
}

// SetString stores a value in memory cache with specified TTL
func (c *MemoryCache) SetString(ctx context.Context, key string, value string, expiration time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.items[key] = &cacheItem{
		value:     value,
		expiresAt: time.Now().Add(expiration),
	}
	return nil
}

// RedisAdapter implements both Cache and RedisClient interfaces
type RedisAdapter struct {
	client RedisClient
}

// SetClient sets the Redis client - used for testing
func (c *RedisAdapter) SetClient(client RedisClient) {
	c.client = client
}

// NewRedisAdapter creates a new Redis adapter
func NewRedisAdapter(client RedisClient) *RedisAdapter {
	return &RedisAdapter{
		client: client,
	}
}

// Get implements both Cache.Get and RedisClient.Get
func (c *RedisAdapter) Get(ctx context.Context, key string) *redis.StringCmd {
	return c.client.Get(ctx, key)
}

// GetString implements Cache.Get by returning the string value
func (c *RedisAdapter) GetString(ctx context.Context, key string) (string, error) {
	return c.Get(ctx, key).Result()
}

// Set implements both Cache.Set and RedisClient.Set
func (c *RedisAdapter) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	return c.client.Set(ctx, key, value, expiration)
}

// SetString implements Cache.Set by returning just the error
func (c *RedisAdapter) SetString(ctx context.Context, key string, value string, expiration time.Duration) error {
	return c.Set(ctx, key, value, expiration).Err()
}



// Close closes the Redis connection
func (c *RedisAdapter) Close() error {
	return c.client.Close()
}
