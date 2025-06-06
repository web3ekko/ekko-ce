package persistence

import (
	"context"
	"fmt"
	"io"
	"path/filepath"
	"strings"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
)

// MinioStorage provides an interface to MinIO object storage
type MinioStorage struct {
	client     *minio.Client
	bucketName string
	basePath   string
}

// MinioConfig contains configuration for MinIO client
type MinioConfig struct {
	Endpoint     string
	AccessKey    string
	SecretKey    string
	UseSSL       bool
	BucketName   string
	BasePath     string
}

// NewMinioStorage creates a new MinIO storage client
func NewMinioStorage(cfg MinioConfig) (*MinioStorage, error) {
	// Initialize MinIO client
	client, err := minio.New(cfg.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.AccessKey, cfg.SecretKey, ""),
		Secure: cfg.UseSSL,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create MinIO client: %w", err)
	}

	storage := &MinioStorage{
		client:     client,
		bucketName: cfg.BucketName,
		basePath:   cfg.BasePath,
	}

	// Ensure bucket exists
	return storage, storage.ensureBucketExists(context.Background())
}

// ensureBucketExists creates the bucket if it doesn't exist
func (ms *MinioStorage) ensureBucketExists(ctx context.Context) error {
	exists, err := ms.client.BucketExists(ctx, ms.bucketName)
	if err != nil {
		return fmt.Errorf("failed to check if bucket %s exists: %w", ms.bucketName, err)
	}

	if !exists {
		err = ms.client.MakeBucket(ctx, ms.bucketName, minio.MakeBucketOptions{})
		if err != nil {
			return fmt.Errorf("failed to create bucket %s: %w", ms.bucketName, err)
		}
	}

	return nil
}

// Upload uploads data to MinIO
func (ms *MinioStorage) Upload(ctx context.Context, objectName string, reader io.Reader, size int64, contentType string) (minio.UploadInfo, error) {
	// Make sure objectName doesn't start with a slash
	objectName = strings.TrimPrefix(objectName, "/")
	
	// Prepend basePath if configured
	if ms.basePath != "" {
		objectName = filepath.Join(ms.basePath, objectName)
	}

	// Upload object
	info, err := ms.client.PutObject(ctx, ms.bucketName, objectName, reader, size, 
		minio.PutObjectOptions{ContentType: contentType})
	
	if err != nil {
		return minio.UploadInfo{}, fmt.Errorf("failed to upload object %s: %w", objectName, err)
	}
	
	return info, nil
}

// Download downloads data from MinIO
func (ms *MinioStorage) Download(ctx context.Context, objectName string) (*minio.Object, error) {
	// Make sure objectName doesn't start with a slash
	objectName = strings.TrimPrefix(objectName, "/")
	
	// Prepend basePath if configured
	if ms.basePath != "" {
		objectName = filepath.Join(ms.basePath, objectName)
	}

	// Get object
	obj, err := ms.client.GetObject(ctx, ms.bucketName, objectName, minio.GetObjectOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to download object %s: %w", objectName, err)
	}
	
	return obj, nil
}

// GetObject is a wrapper for the MinIO GetObject method
func (ms *MinioStorage) GetObject(ctx context.Context, objectName string, opts minio.GetObjectOptions) (*minio.Object, error) {
	// Make sure objectName doesn't start with a slash
	objectName = strings.TrimPrefix(objectName, "/")
	
	// Prepend basePath if configured
	if ms.basePath != "" {
		objectName = filepath.Join(ms.basePath, objectName)
	}
	
	return ms.client.GetObject(ctx, ms.bucketName, objectName, opts)
}

// ListObjects lists objects with the given prefix
func (ms *MinioStorage) ListObjects(ctx context.Context, prefix string, recursive bool) <-chan minio.ObjectInfo {
	// Make sure prefix doesn't start with a slash
	prefix = strings.TrimPrefix(prefix, "/")
	
	// Prepend basePath if configured
	if ms.basePath != "" && prefix != "" {
		prefix = filepath.Join(ms.basePath, prefix)
	}
	
	return ms.client.ListObjects(ctx, ms.bucketName, minio.ListObjectsOptions{
		Prefix:    prefix,
		Recursive: recursive,
	})
}

// BuildObjectPath constructs a proper object path based on the given parameters
func (ms *MinioStorage) BuildObjectPath(network, subnet, vmType string, startBlock, endBlock uint64, 
	startTime, endTime, timestamp string, filename string) string {
	
	return fmt.Sprintf("transactions/network=%s/subnet=%s/vm_type=%s/year=%s/month=%s/day=%s/hour=%s/block_batch=%d-%d/%s",
		network,
		subnet,
		vmType,
		startTime[:4],    // year
		startTime[5:7],   // month
		startTime[8:10],  // day
		startTime[11:13], // hour
		startBlock,
		endBlock,
		filename)
}
