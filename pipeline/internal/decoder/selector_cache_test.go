package decoder_test

import (
	"testing"

	"github.com/go-redis/redismock/v9"
	"github.com/web3ekko/ekko-ce/pipeline/internal/decoder"
)

func TestDecoder_SelectorCache(t *testing.T) {
	// Create mock Redis client using redismock
	db, _ := redismock.NewClientMock()
	
	// Create a Redis adapter with the mock client
	redisAdapter := decoder.NewRedisAdapter(db)
	decoder.NewSelectorCache(redisAdapter, "testchain")

}
