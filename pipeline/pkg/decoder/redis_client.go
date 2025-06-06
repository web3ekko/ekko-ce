package decoder

import (
	"context"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisClientAdapter adapts redis.Client to RedisClient interface
type RedisClientAdapter struct {
	client *redis.Client
}

// NewRedisClientAdapter creates a new Redis client adapter
func NewRedisClientAdapter(client *redis.Client) *RedisClientAdapter {
	return &RedisClientAdapter{
		client: client,
	}
}

// Get implements RedisClient.Get
func (c *RedisClientAdapter) Get(ctx context.Context, key string) *redis.StringCmd {
	return c.client.Get(ctx, key)
}

// GetCmd implements RedisClient.GetCmd
func (c *RedisClientAdapter) GetCmd(ctx context.Context, key string) *redis.StringCmd {
	return c.client.Get(ctx, key)
}

// Set implements RedisClient.Set
func (c *RedisClientAdapter) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	return c.client.Set(ctx, key, value, expiration)
}

// SetCmd implements RedisClient.SetCmd
func (c *RedisClientAdapter) SetCmd(ctx context.Context, key string, value interface{}, expiration time.Duration) *redis.StatusCmd {
	return c.client.Set(ctx, key, value, expiration)
}

// Close implements RedisClient.Close
func (c *RedisClientAdapter) Close() error {
	return c.client.Close()
}

// SIsMember implements RedisClient.SIsMember
func (c *RedisClientAdapter) SIsMember(ctx context.Context, key string, member interface{}) *redis.BoolCmd {
	return c.client.SIsMember(ctx, key, member)
}
