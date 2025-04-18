package main

import (
	"context"
	"fmt"
	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/go-redis/redis/v8"
)

func init() {
	configSpec := service.NewConfigSpec().
		Summary("Decodes Ethereum transaction data using ABIs and templates from Redis").
		Field(service.NewStringField("redis_url").
			Description("Redis connection URL").
			Default("redis://localhost:6379"))

	err := service.RegisterProcessor("decode_tx", configSpec,
		func(conf *service.ParsedConfig, res *service.Resources) (service.Processor, error) {
			redisURL, err := conf.FieldString("redis_url")
			if err != nil {
				return nil, err
			}

			opts, err := redis.ParseURL(redisURL)
			if err != nil {
				return nil, fmt.Errorf("failed to parse Redis URL: %v", err)
			}

			rdb := redis.NewClient(opts)
			return newProcessor(rdb), nil
		})
	if err != nil {
		panic(err)
	}
}

type processor struct {
	rdb *redis.Client
}

// Process implements the service.Processor interface
func (p *processor) Process(ctx context.Context, msg *service.Message) (service.MessageBatch, error) {
	return service.MessageBatch{msg}, nil
}

// Close implements service.Processor interface (no-op for now)
func (p *processor) Close(ctx context.Context) error {
	return nil
}

func newProcessor(rdb *redis.Client) *processor {
	return &processor{rdb: rdb}
}
