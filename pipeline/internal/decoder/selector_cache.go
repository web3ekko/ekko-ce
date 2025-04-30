package decoder

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/ethereum/go-ethereum/accounts/abi"
)

// SelectorCache provides fast access to ABI method selectors
type SelectorCache struct {
	redis    RedisClient
	chainID  string
	cache    sync.Map
	template *Template
}

// NewSelectorCache creates a new selector cache
func NewSelectorCache(redis RedisClient, chainID string) *SelectorCache {
	return &SelectorCache{
		redis:   redis,
		chainID: chainID,
	}
}

// GetSelector retrieves a selector entry from cache or Redis
func (c *SelectorCache) GetSelector(ctx context.Context, selector string) (*SelectorEntry, error) {
	// Try memory cache first
	if entry, ok := c.cache.Load(selector); ok {
		return entry.(*SelectorEntry), nil
	}

	// Try Redis
	key := getRedisKey("sel", c.chainID, selector)
	data, err := c.redis.GetCmd(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("redis get failed: %w", err)
	}

	var entry SelectorEntry
	if err := json.Unmarshal([]byte(data), &entry); err != nil {
		return nil, fmt.Errorf("unmarshal failed: %w", err)
	}

	// Create ABI method
	entry.Method = &abi.Method{
		Name:    entry.Name,
		Inputs:  entry.Inputs,
		Outputs: nil,
	}

	// Cache for future use
	c.cache.Store(selector, &entry)
	return &entry, nil
}

// GetSelectorByAddress tries to get a selector specific to an address
func (c *SelectorCache) GetSelectorByAddress(ctx context.Context, address, selector string) (*SelectorEntry, error) {
	key := getRedisKey("sel", c.chainID, address, selector)
	data, err := c.redis.GetCmd(ctx, key).Result()
	if err != nil {
		return nil, fmt.Errorf("redis get failed: %w", err)
	}

	var entry SelectorEntry
	if err := json.Unmarshal([]byte(data), &entry); err != nil {
		return nil, fmt.Errorf("unmarshal failed: %w", err)
	}

	entry.Method = &abi.Method{
		Name:    entry.Name,
		Inputs:  entry.Inputs,
		Outputs: nil,
	}

	return &entry, nil
}

// SetTemplate sets the current template for decoding
func (c *SelectorCache) SetTemplate(t *Template) {
	c.template = t
}

// Clear clears the in-memory cache
func (c *SelectorCache) Clear() {
	c.cache = sync.Map{}
}
