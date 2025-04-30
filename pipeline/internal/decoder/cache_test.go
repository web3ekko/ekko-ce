package decoder_test

import (
	"context"
	"testing"
	"time"

	"github.com/go-redis/redismock/v9"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/web3ekko/ekko-ce/pipeline/internal/decoder"
)

func TestMemoryCache(t *testing.T) {
	cache := decoder.NewMemoryCache()
	ctx := context.Background()

	// Test setting and getting a value
	key := "test-key"
	value := "test-value"
	expiration := time.Second

	err := cache.SetString(ctx, key, value, expiration)
	assert.NoError(t, err)

	val, err := cache.GetString(ctx, key)
	assert.NoError(t, err)
	assert.Equal(t, value, val)

	// Test expiration
	key = "expiring-key"
	value = "expiring-value"
	expiration = time.Millisecond * 100

	err = cache.SetString(ctx, key, value, expiration)
	assert.NoError(t, err)

	// Wait for expiration
	time.Sleep(expiration * 2)

	// Should return error after expiration
	val, err = cache.GetString(ctx, key)
	assert.Error(t, err)

	// Test non-existent key
	val, err = cache.GetString(ctx, "non-existent")
	assert.Error(t, err)
}

func TestRedisAdapter(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	ctx := context.Background()

	// Test Set and Get
	mock.ExpectSet("key1", "value1", time.Minute).SetVal("OK")
	err := adapter.SetString(ctx, "key1", "value1", time.Minute)
	assert.NoError(t, err)

	mock.ExpectGet("key1").SetVal("value1")
	val, err := adapter.GetString(ctx, "key1")
	assert.NoError(t, err)
	assert.Equal(t, "value1", val)

	// Test expiration
	mock.ExpectSet("key2", "value2", time.Millisecond).SetVal("OK")
	err = adapter.SetString(ctx, "key2", "value2", time.Millisecond)
	assert.NoError(t, err)

	mock.ExpectGet("key2").SetErr(redis.Nil)
	_, err = adapter.GetString(ctx, "key2")
	assert.Error(t, err)

	// Test non-existent key
	mock.ExpectGet("nonexistent").SetErr(redis.Nil)
	_, err = adapter.GetString(ctx, "nonexistent")
	assert.Error(t, err)

	// Ensure all expectations were met
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Error("there were unfulfilled expectations:", err)
	}
}
