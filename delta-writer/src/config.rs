use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::env;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    // Service configuration
    pub service_name: String,
    pub metrics_port: u16,
    
    // NATS configuration
    pub nats_url: String,
    pub nats_subject: String,
    pub nats_consumer_name: String,
    pub nats_stream_name: String,
    
    // MinIO/S3 configuration
    pub s3_endpoint: String,
    pub s3_access_key: String,
    pub s3_secret_key: String,
    pub s3_region: String,
    pub s3_bucket: String,
    pub s3_use_ssl: bool,
    
    // Delta Lake configuration
    pub delta_table_path: String,
    pub batch_size: usize,
    pub flush_interval_seconds: u64,
    pub max_concurrent_writes: usize,
    
    // Processing configuration
    pub worker_threads: usize,
    pub buffer_size: usize,
    pub retry_attempts: usize,
    pub retry_delay_ms: u64,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        dotenvy::dotenv().ok(); // Load .env file if present

        Ok(Config {
            service_name: env::var("SERVICE_NAME")
                .unwrap_or_else(|_| "transactions-writer".to_string()),

            metrics_port: env::var("METRICS_PORT")
                .unwrap_or_else(|_| "9090".to_string())
                .parse()?,

            // NATS configuration
            nats_url: env::var("NATS_URL")
                .unwrap_or_else(|_| "nats://localhost:4222".to_string()),

            nats_subject: env::var("NATS_SUBJECT")
                .unwrap_or_else(|_| "transactions.>".to_string()),

            nats_consumer_name: env::var("NATS_CONSUMER_NAME")
                .unwrap_or_else(|_| "transactions-writer".to_string()),

            nats_stream_name: env::var("NATS_STREAM_NAME")
                .unwrap_or_else(|_| "BLOCKCHAIN".to_string()),

            // MinIO/S3 configuration
            s3_endpoint: env::var("S3_ENDPOINT")
                .unwrap_or_else(|_| "http://localhost:9000".to_string()),

            s3_access_key: env::var("S3_ACCESS_KEY")
                .unwrap_or_else(|_| "minioadmin".to_string()),

            s3_secret_key: env::var("S3_SECRET_KEY")
                .unwrap_or_else(|_| "minioadmin".to_string()),

            // S3 region is not required for MinIO, but some clients expect it
            s3_region: env::var("S3_REGION")
                .unwrap_or_else(|_| "us-east-1".to_string()),

            s3_bucket: env::var("S3_BUCKET")
                .unwrap_or_else(|_| "blockchain-events".to_string()),

            s3_use_ssl: env::var("S3_USE_SSL")
                .unwrap_or_else(|_| "false".to_string())
                .parse()
                .unwrap_or(false),

            // Delta Lake configuration - base path, actual tables will be network/subnet
            delta_table_path: env::var("DELTA_TABLE_BASE_PATH")
                .unwrap_or_else(|_| "events".to_string()),
            
            batch_size: env::var("BATCH_SIZE")
                .unwrap_or_else(|_| "1000".to_string())
                .parse()?,
            
            flush_interval_seconds: env::var("FLUSH_INTERVAL_SECONDS")
                .unwrap_or_else(|_| "30".to_string())
                .parse()?,
            
            max_concurrent_writes: env::var("MAX_CONCURRENT_WRITES")
                .unwrap_or_else(|_| "4".to_string())
                .parse()?,
            
            // Processing configuration
            worker_threads: env::var("WORKER_THREADS")
                .unwrap_or_else(|_| "4".to_string())
                .parse()?,
            
            buffer_size: env::var("BUFFER_SIZE")
                .unwrap_or_else(|_| "10000".to_string())
                .parse()?,
            
            retry_attempts: env::var("RETRY_ATTEMPTS")
                .unwrap_or_else(|_| "3".to_string())
                .parse()?,
            
            retry_delay_ms: env::var("RETRY_DELAY_MS")
                .unwrap_or_else(|_| "1000".to_string())
                .parse()?,
        })
    }
    
    /// Get the full S3 endpoint URL
    pub fn s3_endpoint_url(&self) -> String {
        if self.s3_endpoint.starts_with("http") {
            self.s3_endpoint.clone()
        } else {
            let protocol = if self.s3_use_ssl { "https" } else { "http" };
            format!("{}://{}", protocol, self.s3_endpoint)
        }
    }
    
    /// Get the Delta table URI for a specific network and subnet
    pub fn delta_table_uri(&self, network: &str, subnet: &str) -> String {
        let table_path = format!("{}/{}/{}", self.delta_table_path, network.to_lowercase(), subnet.to_lowercase());

        if table_path.starts_with("s3://") {
            table_path
        } else {
            format!("s3://{}/{}", self.s3_bucket, table_path)
        }
    }

    /// Get the base Delta table URI (for listing all tables)
    pub fn delta_table_base_uri(&self) -> String {
        if self.delta_table_path.starts_with("s3://") {
            self.delta_table_path.clone()
        } else {
            format!("s3://{}/{}", self.s3_bucket, self.delta_table_path)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_config_from_env() {
        // Set test environment variables
        env::set_var("SERVICE_NAME", "test-service");
        env::set_var("METRICS_PORT", "8080");
        env::set_var("BATCH_SIZE", "500");
        
        let config = Config::from_env().unwrap();
        
        assert_eq!(config.service_name, "test-service");
        assert_eq!(config.metrics_port, 8080);
        assert_eq!(config.batch_size, 500);
        
        // Clean up
        env::remove_var("SERVICE_NAME");
        env::remove_var("METRICS_PORT");
        env::remove_var("BATCH_SIZE");
    }
    
    #[test]
    fn test_s3_endpoint_url() {
        let config = Config {
            s3_endpoint: "localhost:9000".to_string(),
            s3_use_ssl: false,
            ..Default::default()
        };
        
        assert_eq!(config.s3_endpoint_url(), "http://localhost:9000");
        
        let config_ssl = Config {
            s3_endpoint: "s3.amazonaws.com".to_string(),
            s3_use_ssl: true,
            ..Default::default()
        };
        
        assert_eq!(config_ssl.s3_endpoint_url(), "https://s3.amazonaws.com");
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            service_name: "transactions-writer".to_string(),
            metrics_port: 9090,
            nats_url: "nats://localhost:4222".to_string(),
            nats_subject: "transactions.>".to_string(),
            nats_consumer_name: "transactions-writer".to_string(),
            nats_stream_name: "transactions".to_string(),
            s3_endpoint: "http://localhost:9000".to_string(),
            s3_access_key: "minioadmin".to_string(),
            s3_secret_key: "minioadmin".to_string(),
            s3_region: "us-east-1".to_string(),
            s3_bucket: "blockchain-events".to_string(),
            s3_use_ssl: false,
            delta_table_path: "events".to_string(),
            batch_size: 1000,
            flush_interval_seconds: 30,
            max_concurrent_writes: 4,
            worker_threads: 4,
            buffer_size: 10000,
            retry_attempts: 3,
            retry_delay_ms: 1000,
        }
    }
}
