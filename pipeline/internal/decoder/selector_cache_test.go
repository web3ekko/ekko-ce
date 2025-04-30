package decoder_test

import (
	"context"
	"fmt"
	"testing"

	"github.com/go-redis/redismock/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/web3ekko/ekko-ce/pipeline/internal/decoder"
	"github.com/ethereum/go-ethereum/accounts/abi"
)

func TestDecoder_SelectorCache(t *testing.T) {
	// Create mock Redis client using redismock
	db, _ := redismock.NewClientMock()
	
	// Create a Redis adapter with the mock client
	redisAdapter := decoder.NewRedisAdapter(db)
	decoder.NewSelectorCache(redisAdapter, "testchain")
}

func TestSelectorCache_GetSelector_Success(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0x1234"
	argType, err := abi.NewType("uint256", "", nil)
	require.NoError(t, err)
	entry := decoder.SelectorEntry{
		Name: "foo",
		Inputs: []abi.Argument{{Name: "bar", Type: argType}},
	}
	template := fmt.Sprintf(`{"name":"%s","inputs":[{"name":"%s","type":"uint256"}]}`, entry.Name, entry.Inputs[0].Name)
	mock.ExpectGet("sel:testchain:"+selector).SetVal(template)

	// First fetch: from Redis
	got, err := cache.GetSelector(ctx, selector)
	require.NoError(t, err)
	assert.Equal(t, entry.Name, got.Name)
	assert.Equal(t, entry.Inputs, got.Inputs)
	assert.NotNil(t, got.Method)
	assert.Equal(t, entry.Name, got.Method.Name)

	// Second fetch: from memory cache, no Redis call
	got2, err := cache.GetSelector(ctx, selector)
	require.NoError(t, err)
	assert.Equal(t, got, got2)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestSelectorCache_GetSelector_RedisError(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0xdead"
	mock.ExpectGet("sel:testchain:"+selector).SetErr(fmt.Errorf("redis error"))
	_, err := cache.GetSelector(ctx, selector)
	assert.Error(t, err)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestSelectorCache_GetSelector_UnmarshalError(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0xdead"
	mock.ExpectGet("sel:testchain:"+selector).SetVal("not-json")
	_, err := cache.GetSelector(ctx, selector)
	assert.Error(t, err)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestSelectorCache_GetSelectorByAddress_Success(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0xcafe"
	address := "0xabcdef"
	argType2, err := abi.NewType("uint256", "", nil)
	require.NoError(t, err)
	entry := decoder.SelectorEntry{
		Name:   "baz",
		Inputs: []abi.Argument{{Name: "qux", Type: argType2}},
	}
	template := fmt.Sprintf(`{"name":"%s","inputs":[{"name":"%s","type":"uint256"}]}`, entry.Name, entry.Inputs[0].Name)
	mock.ExpectGet("sel:testchain:"+address+":"+selector).SetVal(template)

	got, err := cache.GetSelectorByAddress(ctx, address, selector)
	require.NoError(t, err)
	assert.Equal(t, entry.Name, got.Name)
	assert.Equal(t, entry.Inputs, got.Inputs)
	assert.NotNil(t, got.Method)
	assert.Equal(t, entry.Name, got.Method.Name)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestSelectorCache_GetSelectorByAddress_RedisError(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0xcafe"
	address := "0xdead"
	mock.ExpectGet("sel:testchain:"+address+":"+selector).SetErr(fmt.Errorf("redis error"))
	_, err := cache.GetSelectorByAddress(ctx, address, selector)
	assert.Error(t, err)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestSelectorCache_Clear(t *testing.T) {
	db, mock := redismock.NewClientMock()
	adapter := decoder.NewRedisAdapter(db)
	cache := decoder.NewSelectorCache(adapter, "testchain")
	ctx := context.Background()

	selector := "0x1234"
	argType3, err := abi.NewType("uint256", "", nil)
	require.NoError(t, err)
	entry := decoder.SelectorEntry{
		Name:   "foo",
		Inputs: []abi.Argument{{Name: "bar", Type: argType3}},
	}
	template := fmt.Sprintf(`{"name":"%s","inputs":[{"name":"%s","type":"uint256"}]}`, entry.Name, entry.Inputs[0].Name)
	// First fetch caches result
	mock.ExpectGet("sel:testchain:"+selector).SetVal(template)
	got, err := cache.GetSelector(ctx, selector)
	require.NoError(t, err)

	// Clear memory cache
	cache.Clear()

	// Expect Redis call again after clear
	mock.ExpectGet("sel:testchain:"+selector).SetVal(template)
	got2, err := cache.GetSelector(ctx, selector)
	require.NoError(t, err)
	assert.Equal(t, got.Name, got2.Name)
	require.NoError(t, mock.ExpectationsWereMet())
}
