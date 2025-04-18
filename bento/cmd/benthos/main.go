package main

import (
	"context"

	"github.com/benthosdev/benthos/v4/public/service"

	// Import our transaction processor
	_ "github.com/web3ekko/ekko-ce/bento/processors/transaction"
)

func main() {
	service.RunCLI(context.Background())
}
