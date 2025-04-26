package main

import (
	"context"
	"fmt"

	"github.com/benthosdev/benthos/v4/public/service"
	"github.com/go-redis/redis/v8"
)

func init() {
	configSpec := service.NewConfigSpec().
		Summary("Decodes Avalanche C-Chain transaction data using ABIs and templates from Valkey").
		Field(service.NewStringField("valkey_url").
			Description("Valkey connection URL").
			Default("valkey://valkey:6379"))

	err := service.RegisterProcessor("decode_tx", configSpec,
		func(conf *service.ParsedConfig, res *service.Resources) (service.Processor, error) {
			valkeyURL, err := conf.FieldString("valkey_url")
			if err != nil {
				return nil, err
			}

			opts, err := redis.ParseURL(valkeyURL)
			if err != nil {
				return nil, fmt.Errorf("failed to parse Valkey URL: %v", err)
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
