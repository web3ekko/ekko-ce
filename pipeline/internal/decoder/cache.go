package decoder

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// Cache interface for storing ABI signatures
type Cache interface {
	Get(ctx context.Context, key string) (string, error)
	Set(ctx context.Context, key string, value string) error
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

// Get retrieves a value from memory cache
func (c *MemoryCache) Get(ctx context.Context, key string) (string, error) {
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

// Set stores a value in memory cache with 24h TTL
func (c *MemoryCache) Set(ctx context.Context, key string, value string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.items[key] = &cacheItem{
		value:     value,
		expiresAt: time.Now().Add(24 * time.Hour),
	}
	return nil
}

// RedisCache implements a Redis-backed cache
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache creates a new Redis cache
func NewRedisCache(url string) *RedisCache {
	opt, err := redis.ParseURL(url)
	if err != nil {
		opt = &redis.Options{
			Addr: url,
		}
	}
	
	return &RedisCache{
		client: redis.NewClient(opt),
	}
}

// Get retrieves a value from Redis
func (c *RedisCache) Get(ctx context.Context, key string) (string, error) {
	return c.client.Get(ctx, key).Result()
}

// Set stores a value in Redis with 24h TTL
func (c *RedisCache) Set(ctx context.Context, key string, value string) error {
	return c.client.Set(ctx, key, value, 24*time.Hour).Err()
}

// Close closes the Redis connection
func (c *RedisCache) Close() error {
	return c.client.Close()
}
