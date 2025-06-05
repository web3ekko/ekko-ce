package testutils_test

import (
	"context"
	"testing"
	"time"

	"github.com/web3ekko/ekko-ce/pipeline/pkg/testutils"
)

func BenchmarkTestEnvironmentSetup(b *testing.B) {
	start := time.Now()
	ctx := context.Background()
	
	for i := 0; i < b.N; i++ {
		_, _, _, err := testutils.GetTestEnvironment(ctx)
		if err != nil {
			b.Fatalf("Failed to get test environment: %v", err)
		}
		// Clean up occurs automatically between calls
	}
	
	b.ReportMetric(float64(time.Since(start).Milliseconds())/float64(b.N), "ms/op")
}
